// ETS2 Bakım Simülatörü — oyun içi katman + semantik giriş eklentisi
//
// SCS SDK eklentisi olarak oyun tarafından yüklenir (bin\win_x64\plugins).
//  * DXGI Present/Present1/ResizeBuffers kancalanır (MinHook), Dear ImGui ile panel çizilir.
//  * Veriler Python simülatöründen "Local\ETS2BakimState" paylaşılan belleğinden okunur.
//  * Semantik giriş cihazı "ignitionoff" komutunu tetikleyerek motoru resmi yoldan durdurur.
//  * Sürüş modları (ECO / COMFORT / SPORT): gaz girdisine (aforward) değer ekleyip çıkararak pedal haritasını değiştirir.
//  * Durum "Local\ETS2BakimOverlay" bloğuna yazılır (Python katmanın çalıştığını buradan görür).
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>

#include <algorithm>
#include <atomic>
#include <cfloat>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

#include "scssdk_telemetry.h"
#include "scssdk_input.h"
#include "common/scssdk_telemetry_truck_common_channels.h"
#include "MinHook.h"
#include "imgui.h"
#include "imgui_impl_dx11.h"
#include "imgui_impl_win32.h"

#define EBK_VERSION "1.15.0"
#define DLLEXPORT extern "C" __declspec(dllexport)

// ---------------------------------------------------------------- genel durum
static HMODULE g_module = nullptr;
static scs_log_t g_log = nullptr;
static std::atomic<bool> g_shutdown{false};
static std::atomic<bool> g_hooked{false};
static HANDLE g_hook_thread = nullptr;

static void Log(const char* fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    char line[560];
    snprintf(line, sizeof(line), "[ets2bakim] %s", buf);
    if (g_log) g_log(SCS_LOG_TYPE_message, line);
    OutputDebugStringA(line);
}

// ---------------------------------------------------------------- paylaşılan bellek
// Adlar yalnızca testte EBK_STATE_NAME / EBK_OVL_NAME ile değişir: test_host bilgisayarda açık simülatörün
// bloklarına dokunmaz (oyunda bu değişkenler yoktur).
static const wchar_t* ShmName(const wchar_t* env, const wchar_t* def, wchar_t* buf, DWORD n) {
    DWORD len = GetEnvironmentVariableW(env, buf, n);
    return (len > 0 && len < n) ? buf : def;
}
static const wchar_t* StateName() {
    static wchar_t buf[96];
    static const wchar_t* name = ShmName(L"EBK_STATE_NAME", L"Local\\ETS2BakimState", buf, 96);
    return name;
}
static const wchar_t* OvlName() {
    static wchar_t buf[96];
    static const wchar_t* name = ShmName(L"EBK_OVL_NAME", L"Local\\ETS2BakimOverlay", buf, 96);
    return name;
}
static const size_t STATE_HEADER = 64;

struct OvlBlock {
    char magic[8];
    uint32_t version;
    uint32_t frames;
    uint32_t handled_cmd;
    uint32_t flags;
    uint32_t width, height;
    uint32_t reserved;
    char renderer[28];
    char dll_version[32];
    // oyun içi servis menüsünden seçilen işlem (Python uygular, sonucu "r" satırıyla bildirir)
    uint32_t svc_seq;            // ofset 96
    char svc_cmd[160];           // ofset 100: "ad?anahtar=değer&..."
    uint32_t svc_tick;           // ofset 260: gönderim anı (GetTickCount) — eski komutlar uygulanmaz
};
enum { FLAG_HOOKED = 1, FLAG_RENDERING = 2, FLAG_INPUT_REG = 4, FLAG_INPUT_ACTIVE = 8 };

static HANDLE g_ovl_map = nullptr;
static volatile OvlBlock* g_ovl = nullptr;
static HANDLE g_state_map = nullptr;
static const volatile uint8_t* g_state = nullptr;
static size_t g_state_size = 0;
static DWORD g_state_next_try = 0;
static std::atomic<uint32_t> g_flags{0};

static void SetFlag(uint32_t f, bool on) {
    if (on) g_flags |= f; else g_flags &= ~f;
    if (g_ovl) g_ovl->flags = g_flags.load();
}

static void CreateOvlBlock() {
    if (g_ovl) return;
    g_ovl_map = CreateFileMappingW(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, sizeof(OvlBlock), OvlName());
    if (!g_ovl_map) return;
    g_ovl = (volatile OvlBlock*)MapViewOfFile(g_ovl_map, FILE_MAP_ALL_ACCESS, 0, 0, sizeof(OvlBlock));
    if (!g_ovl) return;
    OvlBlock b{};
    memcpy(b.magic, "EBKOVL01", 8);
    b.version = 1;
    strncpy(b.renderer, "DX11", sizeof(b.renderer) - 1);
    strncpy(b.dll_version, EBK_VERSION, sizeof(b.dll_version) - 1);
    memcpy((void*)g_ovl, &b, sizeof(b));
}

static SRWLOCK g_state_lock = SRWLOCK_INIT;

static bool OpenStateBlockLocked() {
    if (g_state) return true;
    DWORD now = GetTickCount();
    if ((int)(now - g_state_next_try) < 0) return false;
    g_state_next_try = now + 1000;
    g_state_map = OpenFileMappingW(FILE_MAP_READ, FALSE, StateName());
    if (!g_state_map) return false;
    g_state = (const volatile uint8_t*)MapViewOfFile(g_state_map, FILE_MAP_READ, 0, 0, 0);
    if (!g_state) { CloseHandle(g_state_map); g_state_map = nullptr; return false; }
    MEMORY_BASIC_INFORMATION mbi{};
    VirtualQuery((LPCVOID)g_state, &mbi, sizeof(mbi));
    g_state_size = mbi.RegionSize;
    return true;
}

static bool OpenStateBlock() {
    if (g_state) return true;
    AcquireSRWLockExclusive(&g_state_lock);
    bool ok = OpenStateBlockLocked();
    ReleaseSRWLockExclusive(&g_state_lock);
    return ok;
}

static uint32_t ReadU32(size_t off) { return *(const volatile uint32_t*)(g_state + off); }

// ---------------------------------------------------------------- simülatör verisi
struct Item { std::string text; char lvl = 'n'; float frac = -1.f; };
struct Hist { float lo = 0, hi = 1; std::vector<float> v; };
struct Warn { char lvl; std::string text; };
struct Event { std::string time; char lvl; std::string text; };

struct SimState {
    bool valid = false;
    bool sound = true;
    int lang = 0;               // 0 tr, 1 en, 2 de
    bool banner_warn = false;   // true: şeritte dikkat uyarıları da gösterilir
    bool hud_sync = true;       // oyunda HUD gizlenince (F3) katman da gizlenir
    int hud_vk = VK_F3;         // oyunun "showhud" tuşu (controls.sii'den simülatör okur)
    int ovl_vk = 0;             // katmanın tuşu (Ayarlar'dan; 0 = gönderilmedi, son kaydedilen kalır)
    std::string ovl_key_name;
    int panel_mode = -1;        // oyun içi panel: 0 otomatik, 1 açık, 2 kapalı (-1 = gönderilmedi)
    std::unordered_map<std::string, Item> k;
    std::vector<Warn> warnings;
    std::vector<Event> events;
    std::vector<std::pair<std::string, float>> breakdown;
    std::vector<std::pair<std::string, std::string>> faults;
    std::vector<std::string> notes;
    std::unordered_map<std::string, Hist> hist;
    float heat[8][5] = {};
    bool has_heat = false;
    float split[3] = {};        // fren enerjisi: servis, retarder, motor freni (%)
    bool has_split = false;
    std::vector<std::pair<std::string, float>> speed_bands;   // hız aralığı -> L/100 km
    std::vector<std::pair<int, float>> gears;                 // vites -> süre %
    struct Plan { std::string name, text; char lvl; };
    std::vector<Plan> plan;
    // servis menüsü: anahtar (seçim için sabit), komut, etiket, ayrıntı, bayrak (h başlık, d kapalı, c onaylı, n normal)
    struct Svc { std::string key, cmd, label, detail; char flag; };
    std::vector<Svc> svc;
    uint32_t res_seq = 0;
    bool res_ok = false;
    std::string res_msg;
    // gösterge lambaları: kimlik (stop, batt, oil, cool, brake, eng, dpf, frost, svc), seviye (w sarı, c kırmızı), etiket
    struct Lamp { std::string id; char lvl; std::string label; };
    std::vector<Lamp> lamps;
    // lastikler (dingil grubu başına): ad, diş metni, diş seviyesi, diş oranı, ayrıntı (basınç/sıcaklık), ayrıntı seviyesi
    struct Tire { std::string name, tread; char tlvl; float frac; std::string detail; char dlvl; std::string key;
                  int wheels = 2, ntires = 2; };
    std::vector<Tire> tires;
};

static SimState g_sim;
static uint32_t g_last_seq = 0xFFFFFFFF;
static uint32_t g_last_beat = 0;
static DWORD g_beat_time = 0;
static bool g_sim_alive = false;
static std::string g_buf;
static int g_lang = 0;
static bool g_hud_sync = true;
static int g_hud_vk = VK_F3;
static int g_ovl_vk = VK_F8;                       // katmanın tuşu: F8 ya da Ayarlar'da seçilen tuş
static std::string g_ovl_key_name = "F8";
static int g_panel_mode = 0;                       // oyun içi panel: 0 otomatik, 1 açık, 2 kapalı (overlay.ini)
static bool g_hud_hidden = false;                 // oyunun HUD'u gizli → katman da gizli
static std::atomic<bool> g_game_paused{true};      // telemetri başlangıçta duraklatılmış durumdadır

static std::vector<std::string> Split(const std::string& s, char sep, size_t max_parts = 0) {
    std::vector<std::string> out;
    size_t start = 0;
    while (true) {
        if (max_parts && out.size() + 1 == max_parts) { out.push_back(s.substr(start)); break; }
        size_t p = s.find(sep, start);
        if (p == std::string::npos) { out.push_back(s.substr(start)); break; }
        out.push_back(s.substr(start, p - start));
        start = p + 1;
    }
    return out;
}

static void SaveLang(int lang);
static void SaveKey(int vk, const std::string& name);
static void SavePanelMode();

// Katmanın tuşu: fare düğmeleri, Esc, Shift/Ctrl/Alt ve Windows tuşları olamaz (kombinasyonlar onlarla yapılır).
static bool ValidOvlKey(int vk) {
    return vk >= 0x08 && vk < 256 && vk != VK_ESCAPE && !(vk >= VK_SHIFT && vk <= VK_MENU) && vk != VK_LWIN &&
           vk != VK_RWIN && !(vk >= VK_LSHIFT && vk <= VK_RMENU);
}

static void ParsePayload(const std::string& data) {
    SimState s;
    s.valid = true;
    size_t pos = 0;
    while (pos < data.size()) {
        size_t nl = data.find('\n', pos);
        if (nl == std::string::npos) nl = data.size();
        std::string line = data.substr(pos, nl - pos);
        pos = nl + 1;
        if (line.size() < 2 || line[1] != '\t') {
            if (line.rfind("cfg\tsound\t", 0) == 0) s.sound = line.back() == '1';
            else if (line.rfind("cfg\tlang\t", 0) == 0) {
                std::string l = line.substr(9);
                s.lang = l == "en" ? 1 : l == "de" ? 2 : 0;
            } else if (line.rfind("cfg\tbanner\t", 0) == 0) s.banner_warn = line.back() == 'w';
            else if (line.rfind("cfg\thudsync\t", 0) == 0) s.hud_sync = line.back() == '1';
            else if (line.rfind("cfg\thudkey\t", 0) == 0) {
                int vk = atoi(line.c_str() + 11);
                if (vk > 0 && vk < 256) s.hud_vk = vk;
            } else if (line.rfind("cfg\tovlkey\t", 0) == 0) {
                auto f = Split(line.substr(11), '\t');
                int vk = f.empty() ? 0 : atoi(f[0].c_str());
                if (ValidOvlKey(vk)) {
                    s.ovl_vk = vk;
                    s.ovl_key_name = f.size() > 1 && !f[1].empty() ? f[1] : "?";
                }
            } else if (line.rfind("cfg\tpanel\t", 0) == 0) {
                std::string m = line.substr(10);
                s.panel_mode = m == "on" ? 1 : m == "off" ? 2 : 0;
            }
            continue;
        }
        char t = line[0];
        auto f = Split(line.substr(2), '\t');
        if (t == 'k' && f.size() >= 4) {
            Item it;
            it.text = f[1];
            it.lvl = f[2].empty() ? 'n' : f[2][0];
            it.frac = (float)atof(f[3].c_str());
            s.k[f[0]] = it;
        } else if (t == 'w' && f.size() >= 2) {
            s.warnings.push_back({f[0] == "crit" ? 'c' : f[0] == "warn" ? 'w' : 'i', f[1]});
        } else if (t == 'e' && f.size() >= 3) {
            s.events.push_back({f[0], f[1] == "crit" ? 'c' : f[1] == "warn" ? 'w' : 'i', f[2]});
        } else if (t == 'b' && f.size() >= 2) {
            s.breakdown.push_back({f[0], (float)atof(f[1].c_str())});
        } else if (t == 'f' && f.size() >= 2) {
            s.faults.push_back({f[0], f[1]});
        } else if (t == 'n' && !f.empty()) {
            s.notes.push_back(f[0]);
        } else if (t == 'h' && f.size() >= 4) {
            Hist h;
            h.lo = (float)atof(f[1].c_str());
            h.hi = (float)atof(f[2].c_str());
            for (auto& v : Split(f[3], ',')) h.v.push_back((float)atof(v.c_str()));
            s.hist[f[0]] = std::move(h);
        } else if (t == 'm' && !f.empty()) {
            auto vals = Split(f[0], ',');
            if (vals.size() == 40) {
                for (int i = 0; i < 40; i++) s.heat[i / 5][i % 5] = (float)atof(vals[i].c_str());
                s.has_heat = true;
            }
        } else if (t == 'x' && !f.empty()) {
            auto vals = Split(f[0], ',');
            if (vals.size() == 3) {
                for (int i = 0; i < 3; i++) s.split[i] = (float)atof(vals[i].c_str());
                s.has_split = true;
            }
        } else if (t == 's' && f.size() >= 2) {
            s.speed_bands.push_back({f[0], (float)atof(f[1].c_str())});
        } else if (t == 'g' && f.size() >= 2) {
            s.gears.push_back({atoi(f[0].c_str()), (float)atof(f[1].c_str())});
        } else if (t == 'p' && f.size() >= 3) {
            s.plan.push_back({f[0], f[1], f[2].empty() ? 'n' : f[2][0]});
        } else if (t == 'u' && f.size() >= 5) {
            s.svc.push_back({f[0], f[1], f[2], f[3], f[4].empty() ? 'n' : f[4][0]});
        } else if (t == 'r' && f.size() >= 3) {
            s.res_seq = (uint32_t)strtoul(f[0].c_str(), nullptr, 10);
            s.res_ok = f[1] == "1";
            s.res_msg = f[2];
        } else if (t == 't' && f.size() >= 3) {
            s.lamps.push_back({f[0], f[1].empty() ? 'w' : f[1][0], f[2]});
        } else if (t == 'y' && f.size() >= 6) {
            s.tires.push_back({f[0], f[1], f[2].empty() ? 'n' : f[2][0], (float)atof(f[3].c_str()), f[4],
                               f[5].empty() ? 'n' : f[5][0]});
            if (f.size() >= 9) {   // grup anahtarı, tekerlek ve lastik sayısı (1.11+)
                auto& tr = s.tires.back();
                tr.key = f[6];
                tr.wheels = std::max(1, atoi(f[7].c_str()));
                tr.ntires = std::max(1, atoi(f[8].c_str()));
            }
        }
    }
    if (s.lang != g_lang) SaveLang(s.lang);   // simülatör kapalıyken de bu dil kullanılsın
    g_lang = s.lang;
    if (s.ovl_vk && (s.ovl_vk != g_ovl_vk || s.ovl_key_name != g_ovl_key_name)) SaveKey(s.ovl_vk, s.ovl_key_name);
    if (s.ovl_vk) { g_ovl_vk = s.ovl_vk; g_ovl_key_name = s.ovl_key_name; }
    if (s.panel_mode >= 0 && s.panel_mode != g_panel_mode) {  // oyunun bir sonraki açılışında uygulanır
        g_panel_mode = s.panel_mode;
        SavePanelMode();
    }
    g_hud_sync = s.hud_sync;
    g_hud_vk = s.hud_vk == g_ovl_vk ? 0 : s.hud_vk;   // HUD tuşu katmanın tuşuyla aynıysa HUD eşleşmesi tuşa bağlanmaz
    if (!g_hud_sync) g_hud_hidden = false;
    g_sim = std::move(s);
}

static void PollState() {
    DWORD now = GetTickCount();
    if (!OpenStateBlock()) { g_sim_alive = false; return; }
    if (memcmp((const void*)g_state, "EBKSTAT1", 8) != 0) { g_sim_alive = false; return; }
    uint32_t beat = ReadU32(24);
    if (beat != g_last_beat) { g_last_beat = beat; g_beat_time = now; }
    g_sim_alive = beat != 0 && (now - g_beat_time) < 3000;
    uint32_t s1 = ReadU32(8);
    if (s1 == g_last_seq || (s1 & 1)) return;
    uint32_t len = ReadU32(12);
    if (len == 0 || STATE_HEADER + len > g_state_size) return;
    g_buf.assign((const char*)(g_state + STATE_HEADER), len);
    MemoryBarrier();
    if (ReadU32(8) != s1) return;  // yazım sırasında okunmuş, sonraki karede tekrar
    g_last_seq = s1;
    ParsePayload(g_buf);
}

static const Item& K(const char* key) {
    static Item empty{"—", 'm', -1.f};
    auto it = g_sim.k.find(key);
    return it == g_sim.k.end() ? empty : it->second;
}

// ---------------------------------------------------------------- semantik giriş (motor durdurma, lastik patlaması)
// Komut girdileri (bool): kod 1 = ignitionoff (kontağı kapat), 2 = engine (motor çalıştır/durdur).
// Eksen girdileri (float): abackward (fren) ve steering (direksiyon). Oyunun karışımlarında semantik değer
// oyuncunun kendi girişine EKLENİR; lastik patlamasında jant sürtmesi (fren) ve çekme/kayma (direksiyon) için.
// Simülatör eksenleri durum bloğu başlığına yazar: 28 float fren (0..1), 32 float direksiyon (-1..1), 36 u32 yazım anı
// (GetTickCount). 500 ms'den eski değer yok sayılır: simülatör kapanır ya da takılırsa etki kendiliğinden kalkar.
static const int CMD_COUNT = 2, AXIS_COUNT = 3, INPUT_COUNT = CMD_COUNT + AXIS_COUNT;   // eksenler: fren, direksiyon, gaz
static const char* const CMD_NAMES[CMD_COUNT] = {"ignitionoff", "engine"};
static const DWORD AXIS_MAX_AGE_MS = 500;
static std::atomic<uint32_t> g_cmd_last{0};
static bool g_cmd_inited = false;
static int g_press_state = 0;      // 0 boşta, 2 bu karede bas, 1 basılı gönderildi
static uint32_t g_press_input = 0;
static uint64_t g_input_frame = 0, g_press_frame = 0;
static bool g_cmd_done_this_frame = false;
static float g_axis_target[AXIS_COUNT] = {}, g_axis_now[AXIS_COUNT] = {}, g_axis_sent[AXIS_COUNT] = {};
static int g_axis_next = 0;        // bu karede sıradaki eksen

static SCSAPI_VOID InputActive(const scs_u8_t active, const scs_context_t) {
    SetFlag(FLAG_INPUT_ACTIVE, active != 0);
    Log("giris cihazi %s", active ? "aktif" : "pasif");
}

static float ReadF32(size_t off) {
    uint32_t u = ReadU32(off);
    float v;
    memcpy(&v, &u, sizeof(v));
    return std::isfinite(v) ? v : 0.f;
}

// ---------------------------------------------------------------- sürüş modları (ECO / COMFORT / SPORT)
// Oyunun gaz kontrolü toplamadır (controls.sii: "mix aforward ... + semantical.aforward?0", "mix forward dforward +
// aforward"): eklenti gaza değer ekleyerek (SPORT: keskin pedal) ya da çıkararak (ECO: güç sınırı, yumuşak gaz, hız
// sınırlayıcı) pedal haritasını değiştirir. Parametreler simülatörden durum başlığıyla gelir (40: mod, 44: en yüksek gaz,
// 48: gaz artış hızı /sn, 52: hız sınırı km/h, 56: pedal eğrisi üssü, 60: yazılma anı). Oyuncunun asıl gazı
// truck.input.throttle kanalından okunur; kanal eklentinin katkısını içeriyorsa son gönderilen katkı çıkarılır
// (hangisi olduğu sürüş sırasında ölçülür). Hız sabitleyici açıkken modlar gaza karışmaz.
//
// Kararlılık (1.15): gönderilen katkı oyuna ve telemetriye bir-iki kare gecikmeyle yansıyabilir. 1.14'te katkı her
// karede yeniden hesaplanıp gönderiliyordu; gecikmede oyuncunun gazı yanlış çıkıyor ve SPORT'ta gaz kare kare salınıyordu
// (gerçek pedalın gürültüsüyle neredeyse her karede bir olay; gaz verip bırakırken oyun takılıyordu). Artık:
//  * yeni değer ancak son gönderilen oturunca hesaplanır (en az THR_SETTLE_FRAMES giriş karesi ve THR_SETTLE_S),
//  * %1'den küçük değişiklik gönderilmez (pedal gürültüsü), %0,4'ten küçük katkı tam sıfırdır,
//  * SPORT eğrisi pedal %3'ü geçince devreye girer, %2'nin altında çıkar (eşikte aç-kapa olmaz),
//  * pedal bırakılınca katkı beklemeden tam sıfıra iner (retarder ve motor freni devreden çıkmaz),
//  * salınım sigortası: gönderilen katkının yönü 1 sn'de 8 kez değişirse model bilinmiyorsa "telemetri katkıyı
//    içermiyor" kabul edilir, biliniyorsa sürüş modu 10 sn gaza karışmaz (oyun günlüğüne yazılır).
struct DriveParams { uint32_t mode = 0; float cap = 1.f, rate = 0.f, vlim = 0.f, curve = 1.f; };
static std::atomic<float> g_tl_input{0.f}, g_tl_eff{0.f}, g_tl_speed{0.f}, g_tl_cruise{0.f};
static std::atomic<uint32_t> g_tl_seen{0};          // telemetri gaz kanalından değer geldi mi
static std::atomic<int> g_drive_mode{0};            // çizim için: 0 kapalı, 1 ECO, 2 COMFORT, 3 SPORT
static DriveParams g_drive_test;                    // yalnızca test (EBK_TEST_DRIVE)
static bool g_drive_test_on = false;
static float g_thr_target = 0.f;                    // son hedef gaz (artış hızı sınırı için)
static int g_thr_model = 0;                         // 0 bilinmiyor (katkı dahil varsayılır), 1 dahil, 2 hariç
static int g_thr_votes1 = 0, g_thr_votes2 = 0;
static const DWORD DRIVE_MAX_AGE_MS = 1500;          // simülatör kapanırsa modlar kendiliğinden devre dışı
static const int THR_SETTLE_FRAMES = 3;              // gönderilen katkının oturması: en az bu kadar giriş karesi
static const double THR_SETTLE_S = 0.035;            // ... ve bu kadar süre
static const float THR_DEADBAND = 0.01f;             // bundan küçük değişiklik gönderilmez
static const float THR_MIN = 0.004f;                 // bundan küçük katkı sıfırdır
static const float SPORT_ON = 0.03f, SPORT_OFF = 0.02f;   // SPORT eğrisinin pedal eşikleri (histerezis)
static const int THR_FLIP_MAX = 8;                   // salınım sigortası: bu kadar yön değişimi ...
static const DWORD THR_FLIP_WINDOW_MS = 1000;        // ... bu süre içinde
static const DWORD THR_BLOCK_MS = 10000;             // sigorta atınca sürüş modunun gaza karışmadığı süre
static int g_thr_since = 1 << 20;                    // son gaz gönderiminden beri geçen giriş karesi
static LARGE_INTEGER g_thr_sent_qpc{};               // son gaz gönderiminin anı
static LARGE_INTEGER g_thr_eval_qpc{};               // son hesabın anı (artış hızı sınırı için)
static bool g_thr_sport_on = false;
static float g_thr_last_in = -1.f;                   // önceki karenin telemetri gaz girdisi (pedal sabit mi)
static float g_thr_last_delta = 0.f;                 // son gönderimdeki değişim (yön)
static DWORD g_thr_flips[THR_FLIP_MAX] = {};         // son yön değişimlerinin anları (halka)
static int g_thr_nflips = 0;
static DWORD g_thr_block_until = 0;                  // 0 değilse sürüş modu bu ana kadar gaza karışmaz
static uint32_t g_thr_events = 0;                    // gönderilen gaz olayı sayısı (test çıktısı ve günlük)

static SCSAPI_VOID OnChannelFloat(const scs_string_t, const scs_u32_t, const scs_value_t* const value, const scs_context_t ctx) {
    float v = (value && value->type == SCS_VALUE_TYPE_float) ? value->value_float.value : 0.f;
    static_cast<std::atomic<float>*>(ctx)->store(std::isfinite(v) ? v : 0.f);
    if (ctx == &g_tl_input) g_tl_seen = 1;
}

static DriveParams ReadDriveParams() {
    if (g_drive_test_on) return g_drive_test;
    DriveParams d;
    if (!OpenStateBlock() || memcmp((const void*)g_state, "EBKSTAT1", 8) != 0) return d;
    if (GetTickCount() - ReadU32(60) > DRIVE_MAX_AGE_MS) return d;
    uint32_t m = ReadU32(40);
    if (m < 1 || m > 3) return d;
    d.mode = m;
    d.cap = std::max(0.2f, std::min(1.f, ReadF32(44)));
    d.rate = std::max(0.f, std::min(20.f, ReadF32(48)));
    d.vlim = std::max(0.f, std::min(200.f, ReadF32(52)));
    d.curve = std::max(0.5f, std::min(3.f, ReadF32(56)));
    return d;
}

// b - a saniye (a hiç kurulmadıysa çok büyük: "çoktan oturdu")
static double QpcSec(const LARGE_INTEGER& a, const LARGE_INTEGER& b) {
    static LARGE_INTEGER fq{};
    if (!fq.QuadPart) QueryPerformanceFrequency(&fq);
    if (!a.QuadPart || !fq.QuadPart) return 1e9;
    return (double)(b.QuadPart - a.QuadPart) / (double)fq.QuadPart;
}

static bool ThrottleBlocked() {
    return g_thr_block_until != 0 && (int)(GetTickCount() - g_thr_block_until) < 0;
}

// her karede bir kez: oyuncunun gazından modun istediği gaza geçmek için oyunda tutulacak katkı (-1..1)
static float DriveThrottle() {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    DriveParams d = ReadDriveParams();
    // prev: oyunun elindeki katkı, yani hesaplanan değil son gönderilen değer
    float input = g_tl_input.load(), eff = g_tl_eff.load(), prev = g_axis_sent[2];
    bool cruise = g_tl_cruise.load() > 0.1f;
    if (g_thr_since < (1 << 20)) g_thr_since++;
    // son gönderilen katkı oyuna ve telemetriye yansıdı mı (yansımadan hesaplanırsa geri besleme salınımı olur)
    bool settled = g_thr_since >= THR_SETTLE_FRAMES && QpcSec(g_thr_sent_qpc, now) >= THR_SETTLE_S;
    bool steady = settled && g_thr_last_in >= 0.f && std::fabs(input - g_thr_last_in) < 0.01f;   // pedal sabit
    g_thr_last_in = input;
    // telemetrinin gaz girdisi eklentinin katkısını içeriyor mu: katkı oturmuşken ve pedal sabitken etkin gazla
    // karşılaştırılır (iki varsayımın farkı katkının kendisidir; göreli eşik küçük katkılarda da karar verir)
    float a = std::fabs(prev);
    if (g_thr_model == 0 && steady && !cruise && a >= 0.02f && eff > 0.02f && eff < 0.98f) {
        float e1 = std::fabs(eff - input), e2 = std::fabs(eff - (input + prev));
        if (e1 < 0.3f * a && e2 > 0.7f * a) g_thr_votes1++;
        else if (e2 < 0.3f * a && e1 > 0.7f * a) g_thr_votes2++;
        if (g_thr_votes1 >= 20 || g_thr_votes2 >= 20) {
            g_thr_model = g_thr_votes1 >= 20 ? 1 : 2;
            Log("surus modu: gaz telemetrisi eklenti katkisini %s", g_thr_model == 1 ? "iceriyor" : "icermiyor");
        }
    }
    float raw = g_thr_model == 2 ? input : input - prev;   // oyuncunun asıl gazı (pedal / klavye)
    raw = std::max(0.f, std::min(1.f, raw));
    if (d.mode == 0 || cruise || !g_tl_seen || ThrottleBlocked()) {
        g_thr_target = raw;
        g_thr_sport_on = false;
        g_thr_eval_qpc = now;
        return 0.f;
    }
    if (!settled) {
        // önceki değer oturana kadar beklenir; pedal bırakıldıysa eklenen gaz beklemeden kalkar
        return (prev > 0.f && raw < SPORT_OFF) ? 0.f : prev;
    }
    float dt = g_thr_eval_qpc.QuadPart ? (float)std::min(0.25, std::max(0.0, QpcSec(g_thr_eval_qpc, now))) : 0.f;
    g_thr_eval_qpc = now;
    // SPORT: keskin pedal; pedal %3'ü geçince devreye girer, %2'nin altında çıkar (bırakırken oyunda gaz kalmaz)
    g_thr_sport_on = d.curve > 1.01f && (raw >= SPORT_ON || (g_thr_sport_on && raw >= SPORT_OFF));
    float t = g_thr_sport_on ? 1.f - std::pow(1.f - raw, d.curve) : raw;
    t = std::min(t, d.cap);                                                  // ECO: güç sınırı
    if (d.vlim > 0.f) t = std::min(t, std::max(0.f, std::min(1.f, (d.vlim - g_tl_speed.load() * 3.6f) / 4.f)));
    if (d.rate > 0.f && t > g_thr_target) t = std::min(t, g_thr_target + d.rate * dt);   // yumuşak gaz
    g_thr_target = t;
    float c = std::max(-1.f, std::min(1.f, t - raw));
    if (std::fabs(c) < THR_MIN) c = 0.f;                       // çok küçük katkı yok: oyunda küçük gaz kalmasın
    else if (std::fabs(c - prev) < THR_DEADBAND) c = prev;    // küçük değişiklik (pedal gürültüsü) gönderilmez
    return c;
}

// gaz katkısı gönderildi: oturma sayacı yeniden başlar; yön değişimleri salınım sigortası için sayılır
static void ThrottleSent(float old_v, float new_v) {
    QueryPerformanceCounter(&g_thr_sent_qpc);
    g_thr_since = 0;
    g_thr_events++;
    float dv = new_v - old_v;
    if (std::fabs(dv) < 0.015f) return;
    if (g_thr_last_delta != 0.f && (dv > 0.f) != (g_thr_last_delta > 0.f)) {
        DWORD now = GetTickCount();
        g_thr_flips[g_thr_nflips % THR_FLIP_MAX] = now;
        g_thr_nflips++;
        // halkadaki en eski kayıt (sıradaki yazılacak yer) 1 sn'den yeniyse son 8 yön değişimi 1 sn içinde olmuştur
        if (g_thr_nflips >= THR_FLIP_MAX && now - g_thr_flips[g_thr_nflips % THR_FLIP_MAX] < THR_FLIP_WINDOW_MS) {
            g_thr_nflips = 0;
            if (g_thr_model == 0) {
                g_thr_model = 2;   // katkı içeriyor varsayımıyla salınıyorsa telemetri katkıyı içermiyordur
                Log("surus modu: gaz salinimi algilandi; telemetri eklenti katkisini icermiyor kabul edildi");
            } else {
                g_thr_block_until = (now + THR_BLOCK_MS) | 1;
                Log("surus modu: gaz salinimi algilandi; surus modu %u sn gaza karismayacak", (unsigned)(THR_BLOCK_MS / 1000));
            }
        }
    }
    g_thr_last_delta = dv;
}

static bool g_axis_force = false;   // bu karede eksenlerin hepsi değişmemiş olsa da gönderilir (cihaz yeniden etkin)

static SCSAPI_RESULT InputEvent(scs_input_event_t* const ev, const scs_u32_t flags, const scs_context_t) {
    if (flags & SCS_INPUT_EVENT_CALLBACK_FLAG_first_in_frame) {
        g_input_frame++;
        g_cmd_done_this_frame = false;
        g_axis_next = 0;
        if (flags & SCS_INPUT_EVENT_CALLBACK_FLAG_first_after_activation) {
            // cihaz yeniden etkinleşti (ör. oyun penceresi odağa döndü): oyun girdileri sıfırlamış olabilir; eksenler
            // yeniden gönderilir ve gaz katkısı yeniden oturana kadar beklenir
            g_axis_force = true;
            g_thr_since = 0;
            QueryPerformanceCounter(&g_thr_sent_qpc);
            g_thr_last_in = -1.f;
        }
        float brake = 0.f, steer = 0.f;
        if (OpenStateBlock() && memcmp((const void*)g_state, "EBKSTAT1", 8) == 0) {
            uint32_t seq = ReadU32(16), code = ReadU32(20);
            if (!g_cmd_inited) { g_cmd_last = seq; g_cmd_inited = true; }
            if (seq != g_cmd_last && seq != 0 && code >= 1 && code <= (uint32_t)CMD_COUNT && g_press_state == 0) {
                g_cmd_last = seq;
                g_press_input = code - 1;
                g_press_state = 2;  // bu karede bas
            } else if (seq != g_cmd_last && g_press_state == 0) {
                g_cmd_last = seq;
            }
            if (GetTickCount() - ReadU32(36) < AXIS_MAX_AGE_MS) {
                brake = std::max(0.f, std::min(1.f, ReadF32(28)));
                steer = std::max(-1.f, std::min(1.f, ReadF32(32)));
            }
        }
        g_axis_target[0] = brake;
        g_axis_target[1] = steer;
        // ani sıçrama olmasın: kare başına sınırlı değişim (fren hızlı, direksiyon yumuşak, gaz kontrolcünün kendi hızında)
        const float step[AXIS_COUNT] = {0.08f, 0.012f, 2.f};   // gaz: kontrolcü zaten yumuşak, gecikme eklenmesin
        g_axis_target[2] = DriveThrottle();
        for (int i = 0; i < AXIS_COUNT; i++) {
            float d = g_axis_target[i] - g_axis_now[i];
            g_axis_now[i] += std::max(-step[i], std::min(step[i], d));
        }
    }
    if (!g_cmd_done_this_frame) {
        if (g_press_state == 2) {
            ev->input_index = g_press_input;
            ev->value_bool.value = 1;
            g_press_state = 1;
            g_press_frame = g_input_frame;
            g_cmd_done_this_frame = true;
            Log("%s komutu gonderildi", CMD_NAMES[g_press_input]);
            return SCS_RESULT_ok;
        }
        if (g_press_state == 1 && g_input_frame >= g_press_frame + 3) {
            ev->input_index = g_press_input;
            ev->value_bool.value = 0;
            g_press_state = 0;
            g_cmd_done_this_frame = true;
            if (g_ovl) g_ovl->handled_cmd = g_cmd_last.load();
            return SCS_RESULT_ok;
        }
        g_cmd_done_this_frame = true;
    }
    while (g_axis_next < AXIS_COUNT) {
        int i = g_axis_next++;
        // sıfır her zaman gönderilir: oyunda küçük bir gaz kalırsa retarder ve motor freni devreden çıkar
        if (g_axis_force || std::fabs(g_axis_now[i] - g_axis_sent[i]) > 0.0005f ||
            (g_axis_now[i] == 0.f && g_axis_sent[i] != 0.f)) {
            ev->input_index = CMD_COUNT + i;
            ev->value_float.value = g_axis_now[i];
            if (i == 2) ThrottleSent(g_axis_sent[i], g_axis_now[i]);
            g_axis_sent[i] = g_axis_now[i];
            return SCS_RESULT_ok;
        }
    }
    g_axis_force = false;
    return SCS_RESULT_not_found;
}

// ---------------------------------------------------------------- katman ayarları (kalıcı)
// corner (Ctrl+F8 sırası): 0 = sol üst, 1 = sağ üst, 2 = sağ alt, 3 = sol alt.
// Fareyle düzenlemede (Ctrl+Alt+F8) panel serbest konuma taşınabilir: free + (fx, fy) panelin tutturulduğu köşe
// noktası (ekran oranı), (fpx, fpy) hangi köşe (0 sol/üst, 1 sağ/alt; panel ekranın hangi yarısındaysa o köşe, böylece
// alttaki panel yukarı doğru uzar). zoom: panel boyutu; lamp_*: gösterge lambası şeridi (alt orta noktası) ve boyutu.
struct Prefs {
    int mode = 1; int page = 0; int corner = 0; int scale = 1;
    float zoom = 1.f;
    bool free = false; float fx = 0.f, fy = 0.f; int fpx = 0, fpy = 0;
    bool lamp_free = false; float lx = 0.5f, ly = 1.f; float lamp_zoom = 1.f;
};
static Prefs g_prefs;
static const float SCALES[] = {0.9f, 1.0f, 1.15f, 1.3f};
static const float ZOOM_MIN = 0.7f, ZOOM_MAX = 2.0f;
static const int PAGE_COUNT = 11;
static const int MODE_COUNT = 3;   // katman tuşu sırası: 0 kapalı, 1 kompakt, 2 detaylı
static const int POS_COUNT = 4;

static float Clampf(float v, float lo, float hi) { return std::min(std::max(v, lo), hi); }

static std::wstring PrefsPath() {
    wchar_t over[MAX_PATH] = L"";
    if (GetEnvironmentVariableW(L"EBK_PREFS_PATH", over, MAX_PATH)) return over;   // yalnızca test: gerçek ayarlara dokunulmaz
    wchar_t base[MAX_PATH] = L"";
    if (!GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH)) return L"";
    std::wstring dir = std::wstring(base) + L"\\ETS2Bakim";
    CreateDirectoryW(dir.c_str(), nullptr);
    return dir + L"\\overlay.ini";
}

static void LoadPrefs() {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    auto rdi = [&](const wchar_t* key, int def) { return (int)GetPrivateProfileIntW(L"overlay", key, def, p.c_str()); };
    auto rdf = [&](const wchar_t* key, float def) {
        wchar_t b[32];
        GetPrivateProfileStringW(L"overlay", key, L"", b, 32, p.c_str());
        return b[0] ? (float)_wtof(b) : def;
    };
    int ver = rdi(L"version", 1);
    int mode = rdi(L"mode", 1);
    g_prefs.mode = mode >= 0 && mode < MODE_COUNT ? mode : 1;   // 1.12'nin CarPlay'i (3) kompakta döner
    g_prefs.page = rdi(L"page", 0) % PAGE_COUNT;
    if (ver >= 2)  // 1. sürümün boyut değerleri yeni düzene uymuyor
        g_prefs.scale = rdi(L"scale", 1) % 4;
    if (ver >= 4)  // 4. sürümde konumlar dört ekran köşesine indirildi (varsayılan: sol üst)
        g_prefs.corner = rdi(L"corner", 0) % POS_COUNT;
    g_prefs.zoom = g_prefs.lamp_zoom = SCALES[g_prefs.scale];
    if (ver >= 5) {  // 5. sürüm: fareyle serbest konum ve sürekli boyut
        g_prefs.zoom = rdf(L"zoom", g_prefs.zoom);
        g_prefs.free = rdi(L"free", 0) != 0;
        g_prefs.fx = rdf(L"fx", 0.f); g_prefs.fy = rdf(L"fy", 0.f);
        g_prefs.fpx = rdi(L"fpx", 0) ? 1 : 0; g_prefs.fpy = rdi(L"fpy", 0) ? 1 : 0;
        g_prefs.lamp_free = rdi(L"lamp_free", 0) != 0;
        g_prefs.lx = rdf(L"lx", 0.5f); g_prefs.ly = rdf(L"ly", 1.f);
        g_prefs.lamp_zoom = rdf(L"lamp_zoom", g_prefs.zoom);
    }
    g_prefs.zoom = Clampf(g_prefs.zoom, ZOOM_MIN, ZOOM_MAX);
    g_prefs.lamp_zoom = Clampf(g_prefs.lamp_zoom, ZOOM_MIN, ZOOM_MAX);
    g_prefs.fx = Clampf(g_prefs.fx, 0.f, 1.f); g_prefs.fy = Clampf(g_prefs.fy, 0.f, 1.f);
    g_prefs.lx = Clampf(g_prefs.lx, 0.f, 1.f); g_prefs.ly = Clampf(g_prefs.ly, 0.f, 1.f);
    wchar_t v[16];
    if (GetEnvironmentVariableW(L"EBK_FORCE_MODE", v, 16)) g_prefs.mode = _wtoi(v) % MODE_COUNT;
    if (GetEnvironmentVariableW(L"EBK_FORCE_PAGE", v, 16)) g_prefs.page = _wtoi(v) % PAGE_COUNT;
    if (GetEnvironmentVariableW(L"EBK_FORCE_CORNER", v, 16)) { g_prefs.corner = _wtoi(v) % POS_COUNT; g_prefs.free = false; }
    if (GetEnvironmentVariableW(L"EBK_FORCE_HUDHIDDEN", v, 16)) g_hud_hidden = _wtoi(v) != 0;
}

static void SavePrefs() {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    auto wi = [&](const wchar_t* key, int val) {
        wchar_t v[16];
        swprintf(v, 16, L"%d", val);
        WritePrivateProfileStringW(L"overlay", key, v, p.c_str());
    };
    auto wf = [&](const wchar_t* key, float val) {
        wchar_t v[32];
        swprintf(v, 32, L"%.4f", val);
        WritePrivateProfileStringW(L"overlay", key, v, p.c_str());
    };
    WritePrivateProfileStringW(L"overlay", L"version", L"5", p.c_str());
    wi(L"mode", g_prefs.mode); wi(L"page", g_prefs.page); wi(L"corner", g_prefs.corner); wi(L"scale", g_prefs.scale);
    wf(L"zoom", g_prefs.zoom);
    wi(L"free", g_prefs.free); wf(L"fx", g_prefs.fx); wf(L"fy", g_prefs.fy); wi(L"fpx", g_prefs.fpx); wi(L"fpy", g_prefs.fpy);
    wi(L"lamp_free", g_prefs.lamp_free); wf(L"lx", g_prefs.lx); wf(L"ly", g_prefs.ly); wf(L"lamp_zoom", g_prefs.lamp_zoom);
}

// Son dil: simülatörden gelen dil kaydedilir; simülatör kapalıyken ("Simülatör çalışmıyor" vb.) de o dil kullanılır.
static void LoadLang() {
    std::wstring p = PrefsPath();
    if (!p.empty()) g_lang = (int)GetPrivateProfileIntW(L"overlay", L"lang", 0, p.c_str()) % 3;
}

static void SaveLang(int lang) {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    wchar_t v[8];
    swprintf(v, 8, L"%d", lang);
    WritePrivateProfileStringW(L"overlay", L"lang", v, p.c_str());
}

static void WriteIniInt(const wchar_t* key, int val) {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    wchar_t v[16];
    swprintf(v, 16, L"%d", val);
    WritePrivateProfileStringW(L"overlay", key, v, p.c_str());
}

// Katmanın tuşu ve oyun içi panel ayarı uygulamadan gelir; oyun açılırken uygulama kapalı olabileceği için saklanır.
static void LoadKeyPanel() {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    int vk = (int)GetPrivateProfileIntW(L"overlay", L"key", VK_F8, p.c_str());
    wchar_t name[64];
    GetPrivateProfileStringW(L"overlay", L"key_name", L"F8", name, 64, p.c_str());
    if (ValidOvlKey(vk) && name[0]) {
        char a[128];
        WideCharToMultiByte(CP_UTF8, 0, name, -1, a, sizeof(a), nullptr, nullptr);
        g_ovl_vk = vk;
        g_ovl_key_name = a;
    }
    int pm = (int)GetPrivateProfileIntW(L"overlay", L"panel", 0, p.c_str());
    g_panel_mode = pm >= 0 && pm <= 2 ? pm : 0;
}

static void SaveKey(int vk, const std::string& name) {
    std::wstring p = PrefsPath();
    if (p.empty()) return;
    wchar_t w[64];
    MultiByteToWideChar(CP_UTF8, 0, name.c_str(), -1, w, 64);
    WriteIniInt(L"key", vk);
    WritePrivateProfileStringW(L"overlay", L"key_name", w, p.c_str());
}

static void SavePanelMode() { WriteIniInt(L"panel", g_panel_mode); }

// Kısayol yazılarındaki "F8" seçilen tuşun adıyla gösterilir.
static std::string KeyText(const char* s) {
    std::string r = s;
    if (g_ovl_key_name == "F8") return r;
    for (size_t i = r.find("F8"); i != std::string::npos; i = r.find("F8", i + g_ovl_key_name.size()))
        r.replace(i, 2, g_ovl_key_name);
    return r;
}

// Oyun içi panel (DXGI kancası) açılışta kurulmadıysa nedeni: katman bloğunun reserved alanında uygulamaya bildirilir
// (alt bayt neden, ikinci bayt bulunan eklenti: 1 OptiScaler, 2 DLSS 5).
enum { SKIP_NONE = 0, SKIP_USER = 1, SKIP_INJECTOR = 2, SKIP_CRASH = 3 };
static uint32_t g_skip = SKIP_NONE;
static bool g_hook_confirmed = false;   // panel sorunsuz çizildi: overlay.ini hook_ok=1
static int g_ok_frames = 0;

// ---------------------------------------------------------------- ImGui / DX11
using PresentFn = HRESULT(STDMETHODCALLTYPE*)(IDXGISwapChain*, UINT, UINT);
using Present1Fn = HRESULT(STDMETHODCALLTYPE*)(IDXGISwapChain1*, UINT, UINT, const DXGI_PRESENT_PARAMETERS*);
using ResizeFn = HRESULT(STDMETHODCALLTYPE*)(IDXGISwapChain*, UINT, UINT, UINT, DXGI_FORMAT, UINT);
static PresentFn oPresent = nullptr;
static Present1Fn oPresent1 = nullptr;
static ResizeFn oResize = nullptr;

static bool g_imgui = false;
static ID3D11Device* g_dev = nullptr;
static ID3D11DeviceContext* g_ctx = nullptr;
static IDXGISwapChain* g_sc = nullptr;
static HWND g_hwnd = nullptr;
static ID3D11RenderTargetView* g_rtv = nullptr;
static ImFont* g_font = nullptr;
static ImFont* g_bold = nullptr;
static thread_local int t_depth = 0;
static int g_capture_after = -1;
static std::wstring g_capture_path;

static void ReleaseRTV() { if (g_rtv) { g_rtv->Release(); g_rtv = nullptr; } }

static DXGI_FORMAT UntypedToUnorm(DXGI_FORMAT f) {
    switch (f) {
        case DXGI_FORMAT_R8G8B8A8_TYPELESS: return DXGI_FORMAT_R8G8B8A8_UNORM;
        case DXGI_FORMAT_B8G8R8A8_TYPELESS: return DXGI_FORMAT_B8G8R8A8_UNORM;
        case DXGI_FORMAT_R10G10B10A2_TYPELESS: return DXGI_FORMAT_R10G10B10A2_UNORM;
        case DXGI_FORMAT_R16G16B16A16_TYPELESS: return DXGI_FORMAT_R16G16B16A16_FLOAT;
        default: return f;
    }
}

static UINT g_bb_w = 0, g_bb_h = 0;  // arka tampon boyutu: çizim alanı her zaman buna eşitlenir

static bool CreateRTV(IDXGISwapChain* sc) {
    ID3D11Texture2D* bb = nullptr;
    if (FAILED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), (void**)&bb)) || !bb) return false;
    D3D11_TEXTURE2D_DESC td;
    bb->GetDesc(&td);
    D3D11_RENDER_TARGET_VIEW_DESC rd{};
    rd.Format = UntypedToUnorm(td.Format);
    rd.ViewDimension = td.SampleDesc.Count > 1 ? D3D11_RTV_DIMENSION_TEXTURE2DMS : D3D11_RTV_DIMENSION_TEXTURE2D;
    HRESULT hr = g_dev->CreateRenderTargetView(bb, &rd, &g_rtv);
    bb->Release();
    g_bb_w = td.Width; g_bb_h = td.Height;
    if (g_ovl) { g_ovl->width = td.Width; g_ovl->height = td.Height; }
    return SUCCEEDED(hr);
}

static void LoadFonts() {
    ImGuiIO& io = ImGui::GetIO();
    wchar_t wdir[MAX_PATH];
    GetWindowsDirectoryW(wdir, MAX_PATH);
    char dir[MAX_PATH * 2];
    WideCharToMultiByte(CP_UTF8, 0, wdir, -1, dir, sizeof(dir), nullptr, nullptr);
    std::string base = std::string(dir) + "\\Fonts\\";
    auto exists = [](const std::string& p) { return GetFileAttributesA(p.c_str()) != INVALID_FILE_ATTRIBUTES; };
    ImFontConfig cfg;
    // Net yazı: yatay çoklu örnekleme kapalı (glifler tam piksele oturur, süzme yumuşatmaz) ve ince
    // çizgiler koyu, yarı saydam zeminde silik görünmesin diye biraz kalınlaştırılır.
    cfg.PixelSnapH = true;
    cfg.OversampleH = 1;
    cfg.OversampleV = 1;
    cfg.RasterizerMultiply = 1.15f;
    const char* regular[] = {"segoeui.ttf", "tahoma.ttf", "arial.ttf"};
    const char* bold[] = {"segoeuib.ttf", "seguisb.ttf", "tahomabd.ttf", "arialbd.ttf"};
    for (auto r : regular) if (!g_font && exists(base + r)) g_font = io.Fonts->AddFontFromFileTTF((base + r).c_str(), 16.f, &cfg);
    for (auto b : bold) if (!g_bold && exists(base + b)) g_bold = io.Fonts->AddFontFromFileTTF((base + b).c_str(), 16.f, &cfg);
    if (!g_font) g_font = io.Fonts->AddFontDefault();
    if (!g_bold) g_bold = g_font;
}

static bool InitImGui(IDXGISwapChain* sc) {
    if (FAILED(sc->GetDevice(__uuidof(ID3D11Device), (void**)&g_dev)) || !g_dev) return false;
    g_dev->GetImmediateContext(&g_ctx);
    DXGI_SWAP_CHAIN_DESC d{};
    sc->GetDesc(&d);
    g_hwnd = d.OutputWindow;
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.LogFilename = nullptr;
    io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange | ImGuiConfigFlags_NoMouse | ImGuiConfigFlags_NoKeyboard;
    ImGui_ImplWin32_Init(g_hwnd);
    ImGui_ImplDX11_Init(g_dev, g_ctx);
    LoadFonts();
    ImGuiStyle& st = ImGui::GetStyle();
    st.WindowRounding = 8.f;
    st.WindowBorderSize = 1.f;
    st.WindowPadding = ImVec2(12, 10);
    st.ItemSpacing = ImVec2(8, 4);
    st.Colors[ImGuiCol_WindowBg] = ImVec4(0.098f, 0.098f, 0.094f, 0.91f);
    st.Colors[ImGuiCol_Border] = ImVec4(1, 1, 1, 0.10f);
    st.Colors[ImGuiCol_Text] = ImVec4(1, 1, 1, 1);
    st.Colors[ImGuiCol_Separator] = ImVec4(1, 1, 1, 0.10f);
    g_sc = sc;
    g_imgui = true;
    SetFlag(FLAG_RENDERING, true);
    Log("katman baslatildi (%ux%u)", d.BufferDesc.Width, d.BufferDesc.Height);
    return true;
}

// ---------------------------------------------------------------- dil tablosu
struct L3 { const char* tr; const char* en; const char* de; };
static const char* X(const L3& s) { return g_lang == 1 ? s.en : g_lang == 2 ? s.de : s.tr; }

static const L3 PAGE_NAMES[PAGE_COUNT] = {
    {"Genel", "Overview", "Übersicht"}, {"Motor", "Engine", "Motor"}, {"Yağ", "Oil", "Öl"},
    {"Soğutma", "Cooling", "Kühlung"}, {"Akü", "Battery", "Batterie"},
    {"Lastik & yakıt", "Tyres & fuel", "Reifen & Kraftstoff"}, {"Sürüş & fren", "Driving & brakes", "Fahrt & Bremsen"},
    {"Yolculuk", "Trip", "Tour"}, {"Bakım planı", "Service plan", "Wartungsplan"}, {"Analiz", "Analysis", "Analyse"},
    {"Arıza & kayıt", "Faults & log", "Defekte & Log"}};
static const L3
    T_TITLE{"ETS2 Bakım", "ETS2 Maintenance", "ETS2 Wartung"},
    T_OFFLINE{"Simülatör çalışmıyor.", "Simulator not running.", "Simulator läuft nicht."},
    T_OFFLINE2{"Masaüstündeki ETS2 Bakım – Tek Oyunculu ya da Çok Oyunculu kısayoluyla simülatörü açın. Veriler buraya otomatik gelir.",
               "Open the simulator with the ETS2 Bakım – Singleplayer or Multiplayer shortcut on your desktop. Data will appear here automatically.",
               "Simulator über die Verknüpfung ETS2 Bakım – Einzelspieler oder Mehrspieler auf dem Desktop starten. Die Daten erscheinen hier automatisch."},
    T_WAITING{"Simülatör çalışıyor, kamyon verisi bekleniyor.", "Simulator running, waiting for truck data.",
              "Simulator läuft, warte auf Lkw-Daten."},
    T_COOL{"Soğutma suyu", "Coolant", "Kühlmittel"}, T_OILT{"Yağ sıcaklığı", "Oil temp.", "Öltemperatur"},
    T_OILP{"Yağ basıncı", "Oil pressure", "Öldruck"}, T_BATT{"Akü", "Battery", "Batterie"},
    T_SOC{"Akü şarjı", "Battery charge", "Batterieladung"}, T_OLIFE{"Yağ ömrü", "Oil life", "Öllebensdauer"},
    T_FREEZE{"Antifriz koruması", "Antifreeze protection", "Frostschutz"}, T_DPF{"DPF doluluğu", "DPF load", "DPF-Beladung"},
    T_HEALTH{"Motor sağlığı", "Engine health", "Motorzustand"},
    T_OLVL{"Yağ seviyesi", "Oil level", "Ölstand"}, T_CLVL{"Soğutma suyu seviyesi", "Coolant level", "Kühlmittelstand"},
    T_RPM{"Devir", "RPM", "Drehzahl"}, T_LOAD{"Yük", "Load", "Last"}, T_POWER{"Güç", "Power", "Leistung"},
    T_FUEL{"Anlık tüketim", "Consumption", "Verbrauch"}, T_EXH{"Egzoz", "Exhaust", "Abgas"}, T_SPEED{"Hız", "Speed", "Tempo"},
    T_S_ENGINE{"MOTOR", "ENGINE", "MOTOR"}, T_ENGINE{"Motor", "Engine", "Motor"}, T_MODEL{"Model", "Model", "Modell"},
    T_DETECT{"Sürüşten algılama", "Detection", "Erkennung"}, T_WEAR{"Aşınma hızı", "Wear rate", "Verschleißrate"},
    T_GBOX{"Şanzıman yağı", "Gearbox oil", "Getriebeöl"}, T_CLUTCH{"Debriyaj", "Clutch", "Kupplung"},
    T_RPMCHART{"Devir (rpm)", "Engine speed (rpm)", "Drehzahl (U/min)"},
    T_OLIFE_REM{"Kalan yağ ömrü", "Remaining oil life", "Verbleibende Öllebensdauer"},
    T_LIMITED{"Sınırlayan: ", "Limited by: ", "Begrenzt durch: "},
    T_S_CRIT{"ÖMRÜ BELİRLEYEN ÖLÇÜTLER", "LIFE CRITERIA", "LEBENSDAUER-KRITERIEN"},
    T_S_COND{"DURUM", "CONDITION", "ZUSTAND"}, T_LEVEL{"Seviye", "Level", "Stand"}, T_PRESSURE{"Basınç", "Pressure", "Druck"},
    T_VISC{"Viskozite", "Viscosity", "Viskosität"}, T_TBN{"TBN", "TBN", "TBN"}, T_SOOT{"İs (soot)", "Soot", "Ruß"},
    T_FE{"Demir (Fe)", "Iron (Fe)", "Eisen (Fe)"}, T_FILTER{"Filtre doluluğu", "Filter load", "Filterbeladung"},
    T_ONOIL{"Bu yağla", "On this oil", "Mit diesem Öl"},
    T_S_LAB{"SON YAĞ ANALİZİ", "LAST OIL ANALYSIS", "LETZTE ÖLANALYSE"},
    T_THERMO{"Termostat", "Thermostat", "Thermostat"}, T_FAN{"Fan", "Fan", "Lüfter"},
    T_SYSP{"Sistem basıncı", "System pressure", "Systemdruck"}, T_ICE{"Buzlanma", "Icing", "Vereisung"},
    T_S_COOLANT{"SOĞUTMA SIVISI", "COOLANT", "KÜHLMITTEL"}, T_TYPE{"Tür", "Type", "Typ"},
    T_GLYCOL{"Antifriz oranı", "Antifreeze ratio", "Frostschutzanteil"}, T_FP{"Donma noktası", "Freezing point", "Gefrierpunkt"},
    T_EXPMIN{"Bölgede beklenen en düşük", "Expected low here", "Erwartetes Minimum"}, T_PH{"pH", "pH", "pH"},
    T_INHIB{"İnhibitör", "Inhibitor", "Inhibitor"}, T_SCALE{"Kireç / korozyon", "Scale / corrosion", "Kalk / Korrosion"},
    T_TEMPS{"Sıcaklıklar (°C)", "Temperatures (°C)", "Temperaturen (°C)"},
    T_VOLT{"Voltaj", "Voltage", "Spannung"}, T_AMP{"Akü akımı", "Battery current", "Batteriestrom"},
    T_BLOAD{"Yük / alternatör", "Load / alternator", "Last / Lichtmaschine"},
    T_SOC2{"Şarj durumu", "State of charge", "Ladezustand"}, T_SOH{"Akü sağlığı", "Battery health", "Batteriezustand"},
    T_CRANK{"Tahmini marş voltajı", "Cranking voltage (est.)", "Anlassspannung (gesch.)"},
    T_MINSOC{"Marş için gereken şarj", "Charge needed to start", "Nötige Ladung für Start"},
    T_BTEMP{"Akü sıcaklığı", "Battery temp.", "Batterietemperatur"}, T_H50{"%50'ye kalan süre", "Time to 50%", "Zeit bis 50 %"},
    T_VOLTCHART{"Akü voltajı (V)", "Battery voltage (V)", "Batteriespannung (V)"},
    T_S_BRAKES{"FRENLER", "BRAKES", "BREMSEN"}, T_BRKT{"Fren sıcaklığı", "Brake temp.", "Bremstemperatur"},
    T_AIR{"Hava basıncı", "Air pressure", "Luftdruck"}, T_MASS{"Toplam kütle (tahmini)", "Gross weight (est.)", "Gesamtgewicht (gesch.)"},
    T_SRVBRK{"Servis freni kullanımı", "Service brake use", "Betriebsbremse genutzt"},
    T_HOTBRK{"Sıcak fren (>300 °C)", "Hot brakes (>300 °C)", "Heiße Bremsen (>300 °C)"},
    T_MAXBRK{"En yüksek fren sıcaklığı", "Peak brake temp.", "Max. Bremstemperatur"},
    T_SPLIT{"Fren enerjisi dağılımı (yolculuk)", "Braking energy split (trip)", "Bremsenergie-Verteilung (Tour)"},
    T_SRV{"Servis freni", "Service brake", "Betriebsbremse"}, T_RET{"Retarder", "Retarder", "Retarder"},
    T_EB{"Motor freni", "Engine brake", "Motorbremse"}, T_ROUTE{"Rota", "Route", "Route"}, T_CARGO{"Yük", "Cargo", "Ladung"},
    T_DIST{"Mesafe", "Distance", "Strecke"}, T_DUR{"Süre", "Duration", "Dauer"}, T_AVGSPD{"Ortalama hız", "Avg. speed", "Ø Tempo"},
    T_AVGCONS{"Ortalama tüketim", "Avg. consumption", "Ø Verbrauch"}, T_FUELCOST{"Yakıt / maliyet", "Fuel / cost", "Kraftstoff / Kosten"},
    T_FUELLVL{"Yakıt", "Fuel", "Kraftstoff"}, T_ADBLUE{"AdBlue", "AdBlue", "AdBlue"}, T_TIRES{"Lastikler", "Tyres", "Reifen"},
    T_RANGE{"Menzil", "Range", "Reichweite"}, T_DOSING{"Püskürtme", "Dosing", "Dosierung"},
    T_S_FUEL{"YAKIT", "FUEL", "KRAFTSTOFF"}, T_S_ADBLUE{"ADBLUE", "ADBLUE", "ADBLUE"},
    T_S_TIRES{"LASTİKLER (DİŞ · BASINÇ · SICAKLIK)", "TYRES (TREAD · PRESSURE · TEMP.)", "REIFEN (PROFIL · DRUCK · TEMP.)"},
    T_GAMEWEAR{"Oyundaki tekerlek hasarı", "In-game wheel damage", "Radschaden im Spiel"},
    T_CO2{"Emisyon", "Emissions", "Emissionen"}, T_IDLE{"Rölanti", "Idling", "Leerlauf"},
    T_SCORE{"Sürüş puanı", "Driving score", "Fahrbewertung"},
    T_S_SPEED{"HIZA GÖRE TÜKETİM (L/100 km)", "CONSUMPTION BY SPEED (L/100 km)", "VERBRAUCH NACH TEMPO (L/100 km)"},
    T_S_GEARS{"VİTES KULLANIMI", "GEAR USAGE", "GANGNUTZUNG"},
    T_S_PLAN{"SIRADAKİ BAKIMLAR (TAHMİNİ)", "UPCOMING SERVICE (ESTIMATED)", "NÄCHSTE WARTUNG (GESCHÄTZT)"},
    T_COST1000{"Bakım gideri / 1000 km", "Service cost / 1000 km", "Wartungskosten / 1000 km"},
    T_COSTTOT{"Toplam bakım gideri", "Total service cost", "Wartungskosten gesamt"},
    T_SCORES{"Sürüş puanı (oturum / toplam)", "Driving score (session / total)", "Fahrbewertung (Sitzung / gesamt)"},
    T_ECO{"Eko bant (1000-1500 rpm)", "Eco band (1000-1500 rpm)", "Eco-Bereich (1000-1500 U/min)"},
    T_IDLESH{"Rölanti oranı", "Idle share", "Leerlaufanteil"}, T_CRUISE{"Hız sabitleyici", "Cruise control", "Tempomat"},
    T_HARSH{"Sert fren", "Harsh braking", "Starkes Bremsen"}, T_LUG{"Düşük devirde tam yük", "Lugging", "Untertourig"},
    T_COLDLOAD{"Soğuk motora yüklenme", "Cold engine load", "Kaltlast"},
    T_HOURS{"Motor saati / mesafe", "Engine hours / distance", "Motorstunden / Strecke"},
    T_AVGLOAD{"Ortalama yük / devir", "Avg. load / rpm", "Ø Last / Drehzahl"},
    T_SHIFTS{"Vites değişimi / 100 km", "Gear shifts / 100 km", "Schaltvorgänge / 100 km"},
    T_STARTS{"Marş / soğuk / başarısız", "Starts / cold / failed", "Starts / kalt / fehlgeschl."},
    T_S_HEAT{"DEVİR x YÜK HARİTASI (BU OTURUM)", "RPM x LOAD MAP (SESSION)", "DREHZAHL x LAST (SITZUNG)"},
    T_NOHEAT{"Henüz motor çalışma verisi yok.", "No engine data yet.", "Noch keine Motordaten."},
    T_HEATAXIS{"Yük % (dikey) x devir (yatay) · toplam %.0f dk", "Load % (vertical) x rpm (horizontal) · total %.0f min",
               "Last % (vertikal) x Drehzahl (horizontal) · gesamt %.0f min"},
    T_S_FAULTS{"AKTİF ARIZALAR", "ACTIVE FAULTS", "AKTIVE DEFEKTE"}, T_NOFAULT{"Arıza yok.", "No faults.", "Keine Defekte."},
    T_S_EVENTS{"SON OLAYLAR", "RECENT EVENTS", "LETZTE EREIGNISSE"},
    T_S_LASTMIN{"SON DAKİKALAR", "LAST MINUTES", "LETZTE MINUTEN"},
    T_COLLECT{"veri toplanıyor…", "collecting data…", "sammle Daten…"},
    T_CRIT{"KRİTİK", "CRITICAL", "KRITISCH"}, T_WARN{"DİKKAT", "WARNING", "ACHTUNG"},
    T_OIL{"Yağ", "Oil", "Öl"},
    T_FOOT1{"F8 mod · Shift+F8 sayfa · Ctrl+F8 köşe · Alt+F8 servis · Ctrl+Alt+F8 fareyle taşı",
            "F8 mode · Shift+F8 page · Ctrl+F8 corner · Alt+F8 service · Ctrl+Alt+F8 move with mouse",
            "F8 Modus · Shift+F8 Seite · Ctrl+F8 Ecke · Alt+F8 Service · Strg+Alt+F8 mit Maus verschieben"},
    T_FOOT2{"F8 mod · Shift+F8 sonraki sayfa · Ctrl+F8 köşe · Ctrl+Shift+F8 boyut · Alt+F8 servis · Ctrl+Alt+F8 fareyle taşı/boyut",
            "F8 mode · Shift+F8 next page · Ctrl+F8 corner · Ctrl+Shift+F8 size · Alt+F8 service · Ctrl+Alt+F8 mouse move/size",
            "F8 Modus · Shift+F8 nächste Seite · Ctrl+F8 Ecke · Ctrl+Shift+F8 Größe · Alt+F8 Service · Strg+Alt+F8 Maus: Position/Größe"},
    // servis menüsü
    T_SVC_TITLE{"SERVİS", "SERVICE", "SERVICE"},
    T_SVC_FOOT{"F8 aşağı · Shift+F8 yukarı · Ctrl+F8 uygula · Alt+F8 kapat",
               "F8 down · Shift+F8 up · Ctrl+F8 apply · Alt+F8 close",
               "F8 runter · Shift+F8 hoch · Ctrl+F8 ausführen · Alt+F8 schließen"},
    T_SVC_CONFIRM{"Onaylamak için tekrar Ctrl+F8", "Press Ctrl+F8 again to confirm", "Zum Bestätigen erneut Ctrl+F8"},
    T_SVC_SENT{"Uygulanıyor…", "Applying…", "Wird ausgeführt…"},
    T_SVC_NOSIM{"Servis için simülatör açık olmalı.", "The simulator must be running for service.",
                "Für den Service muss der Simulator laufen."},
    T_SVC_EMPTY{"Servis listesi bekleniyor…", "Waiting for the service list…", "Warte auf die Serviceliste…"},
    T_SVC_MORE{"… daha fazla madde var (F8 ile kaydırın)", "… more items (scroll with F8)", "… weitere Einträge (mit F8 blättern)"},
    // fareyle düzenleme (Ctrl+Alt+F8)
    T_EDIT_TITLE{"FAREYLE DÜZENLEME", "MOUSE EDIT", "MAUS-BEARBEITUNG"},
    T_EDIT_HINT{"Sürükle: taşı · Tekerlek ya da köşe tutamacı: boyut · Orta tık: sıfırla · Sağ tık, Esc ya da Ctrl+Alt+F8: bitir",
                "Drag: move · Wheel or corner grip: size · Middle click: reset · Right click, Esc or Ctrl+Alt+F8: done",
                "Ziehen: verschieben · Mausrad oder Eckgriff: Größe · Mittelklick: zurücksetzen · Rechtsklick, Esc oder Strg+Alt+F8: fertig"},
    T_EDIT_PANEL{"Panel", "Panel", "Panel"}, T_EDIT_LAMPS{"Gösterge lambaları", "Warning lamps", "Warnleuchten"},
    T_SAMPLE_BATT{"Akü", "Battery", "Batterie"}, T_SAMPLE_OIL{"Yağ", "Oil", "Öl"}, T_SAMPLE_TIRE{"Lastik", "Tyres", "Reifen"},
    // sürüş modları
    T_DM_TITLE{"SÜRÜŞ MODU", "DRIVE MODE", "FAHRMODUS"},
    T_DM_ECO{"Güç %75 · yumuşak gaz · 85 km/h sınır", "Power 75% · soft throttle · 85 km/h limit",
             "Leistung 75 % · sanftes Gas · 85 km/h Begrenzung"},
    T_DM_COMFORT{"Yumuşak gaz tepkisi · güç sınırı yok", "Smooth throttle response · no power limit",
                 "Sanfte Gasannahme · keine Leistungsgrenze"},
    T_DM_SPORT{"Keskin pedal · anında tepki", "Sharp pedal · instant response", "Scharfes Pedal · sofortige Reaktion"};

// ---------------------------------------------------------------- çizim yardımcıları
static ImU32 C(uint32_t rgb, float a = 1.f) {
    return IM_COL32((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255, (int)(a * 255));
}
// durum renkleri: sınırda sarı, kritik kırmızı (koyu, yarı saydam zeminde okunaklı tonlar)
static const uint32_t COL_GOOD = 0x2fbf2f, COL_WARN = 0xffc61a, COL_CRIT = 0xe53935, COL_ACCENT = 0x3987e5;
static const uint32_t COL_TEXT2 = 0xe4e2da, COL_MUTED = 0xc9c6bd, COL_FOOT = 0xb4b1a8, COL_TRACK = 0x3c3c39;
static const uint32_t COL_AQUA = 0x1fb37f, COL_ORANGE = 0xe8692f, COL_CRIT_TXT = 0xff4d4d;
static const uint32_t COL_LAMP_AMBER = 0xffae1a;  // gösterge lambası sarısı (kehribar)

static uint32_t LvlRGB(char l) {
    switch (l) {
        case 'g': return COL_GOOD;
        case 'w': return COL_WARN;
        case 'c': return COL_CRIT_TXT;
        case 'm': return COL_MUTED;
        case 'i': return COL_ACCENT;
        default: return 0xffffff;
    }
}
static uint32_t BarRGB(char l) {
    switch (l) {
        case 'w': return COL_WARN;
        case 'c': return COL_CRIT;
        case 'm': return COL_ACCENT;
        case 'n': return COL_ACCENT;
        default: return COL_GOOD;
    }
}

static float S = 1.f;  // ölçek
static float Px(float v) { return v * S; }
// Yazı boyutu: kesirli piksel boyutları bulanık görünür, bu yüzden tam piksele yuvarlanır; küçük yazılar okunaklı
// kalsın diye 1080p'de en az ~13 px.
static float FS(float size) { return std::max(12.f, std::round(std::max(size, 12.5f) * S)); }

static void TextCol(uint32_t rgb, const char* s, float size = 0.f, ImFont* font = nullptr) {
    ImGui::PushFont(font ? font : g_font, size > 0 ? FS(size) : 0.f);
    ImGui::PushStyleColor(ImGuiCol_Text, C(rgb));
    ImGui::TextUnformatted(s);
    ImGui::PopStyleColor();
    ImGui::PopFont();
}

static void TextRight(uint32_t rgb, const char* s, float size, ImFont* font, float right_edge) {
    float label_end = ImGui::GetItemRectMax().x - ImGui::GetWindowPos().x + Px(10);
    ImGui::PushFont(font, FS(size));
    float w = ImGui::CalcTextSize(s).x;
    ImGui::SameLine(std::max(label_end, right_edge - w));
    ImGui::PushStyleColor(ImGuiCol_Text, C(rgb));
    ImGui::TextUnformatted(s);
    ImGui::PopStyleColor();
    ImGui::PopFont();
}

static void Bar(float frac, char lvl, float width, float h = 5.f) {
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    float hh = Px(h);
    dl->AddRectFilled(p, ImVec2(p.x + width, p.y + hh), C(COL_TRACK), hh * 0.5f);
    if (frac >= 0) {
        float w = std::max(hh, width * std::min(1.f, frac));
        dl->AddRectFilled(p, ImVec2(p.x + w, p.y + hh), C(BarRGB(lvl)), hh * 0.5f);
    }
    ImGui::Dummy(ImVec2(width, hh + Px(3)));
}

// etiket solda, değer sağda (değer durum rengiyle), altında isteğe bağlı çubuk
static void RowText(const char* label, const char* value, char lvl, float width) {
    float x0 = ImGui::GetCursorPosX();
    TextCol(COL_TEXT2, label, 14.f);
    TextRight(LvlRGB(lvl), value, 14.f, g_bold, x0 + width);
}

static void Row(const L3& label, const char* key, float width, bool bar = false) {
    const Item& it = K(key);
    RowText(X(label), it.text.c_str(), it.lvl, width);
    if (bar) Bar(it.frac, it.lvl, width);
}

static void Tile(const L3& label, const char* key, float w, const char* sub_key = nullptr) {
    const Item& it = K(key);
    ImGui::BeginGroup();
    TextCol(COL_MUTED, X(label), 13.f);
    TextCol(LvlRGB(it.lvl == 'g' || it.lvl == 'n' ? 'n' : it.lvl), it.text.c_str(), 20.f, g_bold);
    if (sub_key) TextCol(COL_MUTED, K(sub_key).text.c_str(), 12.5f);
    if (it.frac >= 0) Bar(it.frac, it.lvl, w - Px(6), 4.f);
    else ImGui::Dummy(ImVec2(w - Px(6), Px(7)));
    ImGui::EndGroup();
}

static void Tiles(const L3* labels[], const char* keys[], const char* subs[], int n, float w) {
    float tw = (w - Px(10)) / 2.f;
    ImGui::PushStyleVar(ImGuiStyleVar_CellPadding, ImVec2(Px(2), Px(3)));
    if (ImGui::BeginTable("##tiles", 2, ImGuiTableFlags_SizingFixedFit | ImGuiTableFlags_NoPadOuterX, ImVec2(w, 0))) {
        ImGui::TableSetupColumn("a", ImGuiTableColumnFlags_WidthFixed, tw);
        ImGui::TableSetupColumn("b", ImGuiTableColumnFlags_WidthFixed, tw);
        for (int i = 0; i < n; i++) {
            ImGui::TableNextColumn();
            Tile(*labels[i], keys[i], tw, subs[i]);
        }
        ImGui::EndTable();
    }
    ImGui::PopStyleVar();
}

static void Spark(const L3& title, std::initializer_list<std::pair<const char*, uint32_t>> series, const char* unit,
                  float w, float h) {
    TextCol(COL_TEXT2, X(title), 13.f);
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    float hh = Px(h);
    float lo = 1e9f, hi = -1e9f;
    size_t n = 0;
    for (auto& s : series) {
        auto it = g_sim.hist.find(s.first);
        if (it == g_sim.hist.end()) continue;
        lo = std::min(lo, it->second.lo);
        hi = std::max(hi, it->second.hi);
        n = std::max(n, it->second.v.size());
    }
    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + hh), C(0x262624, 0.95f), Px(4));
    if (n >= 2 && hi > lo) {
        for (int g = 1; g < 3; g++) {
            float y = p.y + hh * g / 3.f;
            dl->AddLine(ImVec2(p.x, y), ImVec2(p.x + w, y), C(0xffffff, 0.07f));
        }
        for (auto& s : series) {
            auto it = g_sim.hist.find(s.first);
            if (it == g_sim.hist.end()) continue;
            auto& v = it->second.v;
            std::vector<ImVec2> pts;
            for (size_t i = 0; i < v.size(); i++) {
                float x = p.x + Px(2) + (w - Px(4)) * i / (float)(v.size() - 1);
                float y = p.y + hh - Px(2) - (hh - Px(4)) * (v[i] - lo) / (hi - lo);
                pts.push_back(ImVec2(x, y));
            }
            dl->AddPolyline(pts.data(), (int)pts.size(), C(s.second), ImDrawFlags_None, Px(2));
            dl->AddCircleFilled(pts.back(), Px(3), C(s.second));
        }
        char buf[64];
        snprintf(buf, sizeof(buf), "%.0f", hi);
        dl->AddText(g_font, FS(12), ImVec2(p.x + Px(4), p.y + Px(1)), C(COL_MUTED), buf);
        snprintf(buf, sizeof(buf), "%.0f %s", lo, unit);
        dl->AddText(g_font, FS(12), ImVec2(p.x + Px(4), p.y + hh - Px(15)), C(COL_MUTED), buf);
    } else {
        dl->AddText(g_font, FS(12.5f), ImVec2(p.x + Px(6), p.y + hh / 2 - Px(7)), C(COL_MUTED), X(T_COLLECT));
    }
    ImGui::Dummy(ImVec2(w, hh + Px(4)));
}

static void Legend(std::initializer_list<std::pair<const char*, uint32_t>> items) {
    bool first = true;
    for (auto& it : items) {
        if (!first) ImGui::SameLine(0, Px(12));
        first = false;
        ImVec2 p = ImGui::GetCursorScreenPos();
        ImGui::GetWindowDrawList()->AddRectFilled(ImVec2(p.x, p.y + Px(8)), ImVec2(p.x + Px(12), p.y + Px(10)), C(it.second), Px(1));
        ImGui::Dummy(ImVec2(Px(15), Px(4)));
        ImGui::SameLine(0, Px(2));
        TextCol(COL_TEXT2, it.first, 12.5f);
    }
}

static void Heatmap(float w, float h) {
    static const char* rpm[8] = {"<800", "800", "1000", "1200", "1400", "1600", "1800", "2000+"};
    static const char* load[5] = {"0-20", "20-40", "40-60", "60-80", "80+"};
    static const uint32_t seq[7] = {0x0d366b, 0x104281, 0x184f95, 0x256abf, 0x3987e5, 0x6da7ec, 0xb7d3f6};
    if (!g_sim.has_heat) { TextCol(COL_MUTED, X(T_NOHEAT), 12.5f); return; }
    float mx = 0, tot = 0;
    for (auto& c : g_sim.heat) for (float v : c) { mx = std::max(mx, v); tot += v; }
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    float lw = Px(38), bh = Px(16);
    float cw = (w - lw) / 8.f, ch = (Px(h) - bh) / 5.f;
    for (int c = 0; c < 8; c++)
        for (int r = 0; r < 5; r++) {
            float v = g_sim.heat[c][r];
            uint32_t col = 0x383835;
            if (v > 0 && mx > 0) col = seq[std::min(6, (int)(std::sqrt(v / mx) * 7))];
            ImVec2 a(p.x + lw + c * cw + 1, p.y + (4 - r) * ch + 1);
            dl->AddRectFilled(a, ImVec2(a.x + cw - 2, a.y + ch - 2), C(col), Px(3));
        }
    for (int r = 0; r < 5; r++)
        dl->AddText(g_font, FS(11.5f), ImVec2(p.x, p.y + (4 - r) * ch + ch / 2 - Px(7)), C(COL_MUTED), load[r]);
    for (int c = 0; c < 8; c++)
        dl->AddText(g_font, FS(11), ImVec2(p.x + lw + c * cw + Px(1), p.y + 5 * ch + Px(2)), C(COL_MUTED), rpm[c]);
    ImGui::Dummy(ImVec2(w, Px(h)));
    char buf[160];
    snprintf(buf, sizeof(buf), X(T_HEATAXIS), tot);
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    TextCol(COL_MUTED, buf, 12.f);
    ImGui::PopTextWrapPos();
}

// yatay çubuk listesi (hıza göre tüketim, vites kullanımı)
static void HBars(const std::vector<std::pair<std::string, float>>& rows, float w, const char* fmt, uint32_t col) {
    float mx = 0;
    for (auto& r : rows) mx = std::max(mx, r.second);
    if (rows.empty() || mx <= 0) { TextCol(COL_MUTED, X(T_COLLECT), 12.5f); return; }
    float lw = Px(52), vw = Px(46);
    for (auto& r : rows) {
        ImVec2 p = ImGui::GetCursorScreenPos();
        ImDrawList* dl = ImGui::GetWindowDrawList();
        float bh = Px(10), bw = (w - lw - vw) * r.second / mx;
        ImGui::PushFont(g_font, FS(12.5f));
        dl->AddText(ImVec2(p.x, p.y), C(COL_TEXT2), r.first.c_str());
        char buf[32];
        snprintf(buf, sizeof(buf), fmt, r.second);
        float tw = ImGui::CalcTextSize(buf).x;
        dl->AddText(ImVec2(p.x + w - tw, p.y), C(0xffffff), buf);
        ImGui::PopFont();
        float y = p.y + Px(4);
        dl->AddRectFilled(ImVec2(p.x + lw, y), ImVec2(p.x + w - vw, y + bh), C(COL_TRACK), Px(3));
        dl->AddRectFilled(ImVec2(p.x + lw, y), ImVec2(p.x + lw + std::max(Px(3), bw), y + bh), C(col), Px(3));
        ImGui::Dummy(ImVec2(w, Px(18)));
    }
}

static void Section(const L3& title) {
    ImGui::Dummy(ImVec2(1, Px(3)));
    TextCol(COL_MUTED, X(title), 12.f, g_bold);
}

// ---------------------------------------------------------------- konum ve sığdırma
struct Slot { ImVec2 pos; ImVec2 pivot; float maxh; };
// son karede çizilen panel ve lamba şeridi dikdörtgenleri (fareyle düzenlemede tıklama/sürükleme hedefi)
static ImVec2 g_panel_a, g_panel_b, g_lamp_a, g_lamp_b;
static bool g_panel_ok = false, g_lamp_ok = false;
static bool g_edit = false;   // fareyle düzenleme modu (Ctrl+Alt+F8)

static void PanelPivot(int& px, int& py) {
    if (g_prefs.free) { px = g_prefs.fpx; py = g_prefs.fpy; return; }
    px = (g_prefs.corner == 1 || g_prefs.corner == 2) ? 1 : 0;
    py = (g_prefs.corner == 2 || g_prefs.corner == 3) ? 1 : 0;
}

static Slot GetSlot(const ImVec2& disp, float pw) {
    float k = disp.y / 1080.f;
    float m = 16 * k, maxh = disp.y - 2 * m;
    if (g_prefs.free) {  // fareyle taşınmış: tutturma köşesi ekranda kalır, panel o köşeden büyür
        float px = (float)g_prefs.fpx, py = (float)g_prefs.fpy;
        float lo = m + px * pw, hi = std::max(lo, disp.x - m - (1 - px) * pw);
        float x = Clampf(g_prefs.fx * disp.x, lo, hi);
        float y = Clampf(g_prefs.fy * disp.y, m, disp.y - m);
        float avail = py > 0 ? y - m : disp.y - m - y;
        return {ImVec2(std::round(x), std::round(y)), ImVec2(px, py), std::max(avail, 200 * k)};
    }
    switch (g_prefs.corner) {
        case 1: return {ImVec2(disp.x - m, m), ImVec2(1, 0), maxh};            // sağ üst
        case 2: return {ImVec2(disp.x - m, disp.y - m), ImVec2(1, 1), maxh};   // sağ alt
        case 3: return {ImVec2(m, disp.y - m), ImVec2(0, 1), maxh};            // sol alt
        default: return {ImVec2(m, m), ImVec2(0, 0), maxh};                     // sol üst
    }
}

static const int FIT_SERVICE = PAGE_COUNT + 1;   // 0 kompakt, 1..PAGE_COUNT sayfalar, servis menüsü
static float g_fit[PAGE_COUNT + 2];
static bool g_fit_init = false;

// içerik yüksekliğine göre sayfa ölçeğini ayarlar (bir sonraki karede uygulanır)
static void UpdateFit(int key, float content_h, float maxh) {
    if (content_h <= 0) return;
    float f = g_fit[key] * maxh / content_h;
    g_fit[key] = std::max(0.6f, std::min(1.f, f * 0.985f));
}

static const ImGuiWindowFlags OVL_FLAGS = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs |
                                          ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoFocusOnAppearing |
                                          ImGuiWindowFlags_NoSavedSettings;

static const char* DRIVE_NAMES[4] = {"", "ECO", "COMFORT", "SPORT"};
static uint32_t DriveRGB(int m) { return m == 1 ? COL_GOOD : m == 3 ? COL_ORANGE : COL_ACCENT; }

static void Header(float w) {
    float x0 = ImGui::GetCursorPosX();
    TextCol(0xffffff, K("truck").text.c_str(), 15.5f, g_bold);
    int dm = g_drive_mode.load();
    if (dm >= 1 && dm <= 3) {  // sürüş modu etiketi: kamyon adının yanında
        ImVec2 a = ImGui::GetItemRectMax(), b = ImGui::GetItemRectMin();
        float fs = FS(11.f), h = a.y - b.y;
        ImVec2 ts = g_bold->CalcTextSizeA(fs, FLT_MAX, 0.f, DRIVE_NAMES[dm]);
        ImVec2 p0(a.x + Px(8), b.y + (h - ts.y - Px(4)) * 0.5f);
        ImDrawList* dl = ImGui::GetWindowDrawList();
        dl->AddRectFilled(p0, ImVec2(p0.x + ts.x + Px(10), p0.y + ts.y + Px(4)), C(DriveRGB(dm), 0.22f), Px(4));
        dl->AddRect(p0, ImVec2(p0.x + ts.x + Px(10), p0.y + ts.y + Px(4)), C(DriveRGB(dm), 0.9f), Px(4));
        dl->AddText(g_bold, fs, ImVec2(p0.x + Px(5), p0.y + Px(2)), C(DriveRGB(dm)), DRIVE_NAMES[dm]);
    }
    TextRight(LvlRGB(K("run").lvl), K("run").text.c_str(), 13.5f, g_bold, x0 + w);
    char buf[256];
    snprintf(buf, sizeof(buf), "%s · %s · %s", K("time").text.c_str(), K("loc").text.c_str(), K("amb").text.c_str());
    TextCol(COL_MUTED, buf, 12.5f);
}

static void SimOffline(float w) {
    TextCol(0xffffff, X(T_TITLE), 15.5f, g_bold);
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    TextCol(COL_WARN, X(T_OFFLINE), 13.5f);
    TextCol(COL_MUTED, X(T_OFFLINE2), 12.5f);
    ImGui::PopTextWrapPos();
}

static bool Waiting(float w) {
    auto it = g_sim.k.find("waiting");
    if (it == g_sim.k.end()) return false;
    TextCol(0xffffff, X(T_TITLE), 15.5f, g_bold);
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    TextCol(COL_TEXT2, X(T_WAITING), 13.5f);
    TextCol(COL_MUTED, it->second.text.c_str(), 12.5f);
    ImGui::PopTextWrapPos();
    return true;
}

static void BeginPanel(const char* id, const ImVec2& disp, float w, int fit_key, Slot& slot) {
    if (!g_fit_init) {
        for (auto& f : g_fit) f = 1.f;
        g_fit_init = true;
    }
    S *= g_fit[fit_key];
    float pw = Px(w) + Px(24);
    slot = GetSlot(disp, pw);
    ImGui::SetNextWindowPos(slot.pos, ImGuiCond_Always, slot.pivot);
    ImGui::SetNextWindowSize(ImVec2(pw, 0));
    ImGui::SetNextWindowSizeConstraints(ImVec2(0, 0), ImVec2(FLT_MAX, slot.maxh));
    ImGui::Begin(id, nullptr, OVL_FLAGS);
}

static void EndPanel(int fit_key, const Slot& slot, float base_s) {
    float content = ImGui::GetCursorPosY() + ImGui::GetStyle().WindowPadding.y;
    ImVec2 wp = ImGui::GetWindowPos(), ws = ImGui::GetWindowSize();
    g_panel_a = wp;
    g_panel_b = ImVec2(wp.x + ws.x, wp.y + ws.y);
    g_panel_ok = true;
    ImGui::End();
    UpdateFit(fit_key, content, slot.maxh);
    S = base_s;
}

static void DrawCompact(const ImVec2& disp) {
    float base = S;
    Slot slot;
    BeginPanel("##ebk_compact", disp, 268, 0, slot);
    float w = Px(268);
    if (!g_sim_alive || !g_sim.valid) { SimOffline(w); EndPanel(0, slot, base); return; }
    if (Waiting(w)) { EndPanel(0, slot, base); return; }
    Header(w);
    ImGui::Dummy(ImVec2(1, Px(2)));
    Row(T_COOL, "cool", w, true);
    Row(T_OILT, "oilt", w, true);
    Row(T_OILP, "oilp", w, true);
    Row(T_BATT, "volt", w);
    Row(T_SOC, "soc", w, true);
    Row(T_OLIFE, "olife", w, true);
    Row(T_FREEZE, "freeze", w);
    if (K("dpf").lvl != 'm') Row(T_DPF, "dpf", w, true);
    Row(T_HEALTH, "health", w, true);
    Row(T_FUELLVL, "fuel_lvl", w, true);
    if (K("adblue").lvl != 'm') Row(T_ADBLUE, "adblue", w, true);
    if (!g_sim.tires.empty()) Row(T_TIRES, "tire", w);
    int shown = 0;
    for (auto& wr : g_sim.warnings) {
        if (wr.lvl == 'i' || shown >= 2) continue;
        if (!shown) ImGui::Separator();
        ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
        TextCol(wr.lvl == 'c' ? COL_CRIT_TXT : COL_WARN, wr.text.c_str(), 13.f, wr.lvl == 'c' ? g_bold : g_font);
        ImGui::PopTextWrapPos();
        shown++;
    }
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    TextCol(COL_FOOT, KeyText(X(T_FOOT1)).c_str(), 11.5f);
    ImGui::PopTextWrapPos();
    EndPanel(0, slot, base);
}

static void PageGenel(float w) {
    const L3* l[8] = {&T_COOL, &T_OILT, &T_OILP, &T_BATT, &T_SOC, &T_OLIFE, &T_HEALTH, &T_DPF};
    const char* k[8] = {"cool", "oilt", "oilp", "volt", "soc", "olife", "health", "dpf"};
    const char* s[8] = {"thermo", "visc", nullptr, "amp", "crank", "olim", "wear", "ash"};
    Tiles(l, k, s, 8, w);
    Section(T_S_LASTMIN);
    Legend({{X(T_COOL), COL_ACCENT}, {X(T_OIL), COL_ORANGE}});
    Spark(T_TEMPS, {{"cool", COL_ACCENT}, {"oil_t", COL_ORANGE}}, "°C", w, 46);
}

static void PageMotor(float w) {
    const L3* l[6] = {&T_RPM, &T_LOAD, &T_POWER, &T_FUEL, &T_EXH, &T_SPEED};
    const char* k[6] = {"rpm", "load", "power", "fuel", "exh", "speed"};
    const char* s[6] = {"gear", nullptr, "torque", "l100", "ret", nullptr};
    Tiles(l, k, s, 6, w);
    Section(T_S_ENGINE);
    Row(T_ENGINE, "engine", w);
    Row(T_MODEL, "model", w);
    Row(T_DETECT, "detect", w);
    Row(T_HEALTH, "health", w, true);
    Row(T_WEAR, "wear", w);
    if (g_sim.k.count("gbox")) {             // 1.10+: şanzıman yağı sıcaklığı ve debriyaj (eski simülatör göndermez)
        Row(T_GBOX, "gbox", w, true);
        Row(T_CLUTCH, "clutch", w, true);
    }
    Spark(T_RPMCHART, {{"rpm", COL_ACCENT}}, "rpm", w, 42);
}

static void PageYag(float w) {
    TextCol(COL_MUTED, X(T_OLIFE_REM), 12.5f);
    float x0 = ImGui::GetCursorPosX();
    TextCol(LvlRGB(K("olife").lvl), K("olife").text.c_str(), 28.f, g_bold);
    ImGui::SameLine(x0 + Px(92));
    ImGui::BeginGroup();
    ImGui::PushTextWrapPos(x0 + w);
    TextCol(COL_TEXT2, K("grade").text.c_str(), 13.f);
    std::string lim = std::string(X(T_LIMITED)) + K("olim").text;
    TextCol(COL_MUTED, lim.c_str(), 12.5f);
    ImGui::PopTextWrapPos();
    ImGui::EndGroup();
    Section(T_S_CRIT);
    for (auto& b : g_sim.breakdown) {
        char pct[16];
        snprintf(pct, sizeof(pct), g_lang == 0 ? "%%%.0f" : g_lang == 1 ? "%.0f%%" : "%.0f %%", b.second);
        char lvl = b.second >= 30 ? 'g' : b.second >= 10 ? 'w' : 'c';
        RowText(b.first.c_str(), pct, lvl, w);
        Bar(b.second / 100.f, lvl, w, 4.f);
    }
    Section(T_S_COND);
    Row(T_LEVEL, "olvl", w, true);
    Row(T_PRESSURE, "oilp", w);
    Row(T_VISC, "visc", w);
    Row(T_TBN, "tbn", w);
    Row(T_SOOT, "soot", w);
    Row(T_FE, "fe", w);
    Row(T_FILTER, "filter", w);
    Row(T_ONOIL, "okm", w);
    if (!g_sim.notes.empty()) {
        Section(T_S_LAB);
        ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
        for (auto& n : g_sim.notes) TextCol(COL_TEXT2, ("• " + n).c_str(), 12.5f);
        ImGui::PopTextWrapPos();
    }
}

static void PageSogutma(float w) {
    Row(T_COOL, "cool", w, true);
    Row(T_OILT, "oilt", w, true);
    Row(T_THERMO, "thermo", w);
    Row(T_FAN, "fan", w);
    Row(T_SYSP, "sysp", w);
    Row(T_ICE, "ice", w);
    Section(T_S_COOLANT);
    Row(T_TYPE, "ctype", w);
    Row(T_LEVEL, "clvl", w, true);
    Row(T_GLYCOL, "glycol", w);
    Row(T_FP, "freeze", w);
    Row(T_EXPMIN, "expmin", w);
    Row(T_PH, "ph", w);
    Row(T_INHIB, "inhib", w);
    Row(T_SCALE, "scale", w);
    Legend({{X(T_COOL), COL_ACCENT}, {X(T_OIL), COL_ORANGE}});
    Spark(T_TEMPS, {{"cool", COL_ACCENT}, {"oil_t", COL_ORANGE}}, "°C", w, 44);
}

static void PageAku(float w) {
    Row(T_VOLT, "volt", w, true);
    Row(T_AMP, "amp", w);
    Row(T_BLOAD, "bload", w);
    Row(T_SOC2, "soc", w, true);
    Row(T_SOH, "soh", w, true);
    Row(T_CRANK, "crank", w);
    Row(T_MINSOC, "minsoc", w);
    Row(T_BTEMP, "btemp", w);
    Row(T_H50, "h50", w);
    Spark(T_VOLTCHART, {{"volt", COL_ACCENT}}, "V", w, 44);
}

static void PageLastik(float w) {
    Section(T_S_TIRES);
    for (const auto& t : g_sim.tires) {
        RowText(t.name.c_str(), t.tread.c_str(), t.tlvl, w);
        Bar(t.frac, t.tlvl, w, 4.f);
        TextCol(t.dlvl == 'w' || t.dlvl == 'c' ? LvlRGB(t.dlvl) : COL_MUTED, t.detail.c_str(), 12.5f);
    }
    Row(T_GAMEWEAR, "tire_game", w);
    Section(T_S_FUEL);
    Row(T_FUELLVL, "fuel_lvl", w, true);
    Row(T_RANGE, "fuel_range", w);
    Row(T_AVGCONS, "fuel_avg", w);
    if (K("adblue").lvl != 'm') {
        Section(T_S_ADBLUE);
        Row(T_LEVEL, "adblue", w, true);
        Row(T_DOSING, "adblue_rate", w);
        Row(T_RANGE, "adblue_range", w);
    }
}

static void PageSurus(float w) {
    Section(T_S_BRAKES);
    Row(T_BRKT, "btmp", w, true);
    Row(T_AIR, "air", w, true);
    Row(T_MASS, "mass", w);
    Row(T_SRVBRK, "srvbrk", w);
    Row(T_HOTBRK, "hotbrk", w);
    Row(T_MAXBRK, "maxbrk", w);
    Section(T_SPLIT);
    if (g_sim.has_split) {
        ImVec2 p = ImGui::GetCursorScreenPos();
        ImDrawList* dl = ImGui::GetWindowDrawList();
        const uint32_t cols[3] = {COL_ORANGE, COL_ACCENT, COL_AQUA};
        float x = p.x, h = Px(12);
        for (int i = 0; i < 3; i++) {
            float seg = w * g_sim.split[i] / 100.f;
            if (seg > 0.5f) dl->AddRectFilled(ImVec2(x, p.y), ImVec2(x + seg - Px(2), p.y + h), C(cols[i]), Px(3));
            x += seg;
        }
        ImGui::Dummy(ImVec2(w, h + Px(4)));
        char a[48], b[48], c[48];
        snprintf(a, sizeof(a), "%s %.0f%%", X(T_SRV), g_sim.split[0]);
        snprintf(b, sizeof(b), "%s %.0f%%", X(T_RET), g_sim.split[1]);
        snprintf(c, sizeof(c), "%s %.0f%%", X(T_EB), g_sim.split[2]);
        Legend({{a, cols[0]}, {b, cols[1]}, {c, cols[2]}});
    } else {
        TextCol(COL_MUTED, X(T_COLLECT), 12.5f);
    }
}

static void PageYolculuk(float w) {
    Row(T_ROUTE, "trip_route", w);
    Row(T_CARGO, "trip_cargo", w);
    Row(T_DIST, "trip_dist", w);
    Row(T_DUR, "trip_time", w);
    Row(T_AVGSPD, "trip_avgspd", w);
    Row(T_AVGCONS, "trip_l100", w);
    Row(T_FUELCOST, "trip_fuel", w);
    Row(T_CO2, "trip_co2", w);
    Row(T_IDLE, "trip_idle", w);
    Row(T_SCORE, "trip_score", w);
    Section(T_S_SPEED);
    HBars(g_sim.speed_bands, w, "%.1f", COL_ACCENT);
    Section(T_S_GEARS);
    std::vector<std::pair<std::string, float>> gears;
    for (auto& g : g_sim.gears) gears.push_back({std::to_string(g.first), g.second});
    std::sort(gears.begin(), gears.end(), [](auto& a, auto& b) { return std::stoi(a.first) < std::stoi(b.first); });
    HBars(gears, w, "%.0f%%", COL_AQUA);
}

static void PagePlan(float w) {
    Section(T_S_PLAN);
    for (auto& p : g_sim.plan) RowText(p.name.c_str(), p.text.c_str(), p.lvl, w);
    Row(T_COST1000, "cost1000", w);
    Row(T_COSTTOT, "cost", w);
}

static void PageAnaliz(float w) {
    TextCol(COL_MUTED, X(T_SCORES), 12.5f);
    float x0 = ImGui::GetCursorPosX();
    TextCol(LvlRGB(K("score_s").lvl), K("score_s").text.c_str(), 28.f, g_bold);
    ImGui::SameLine(x0 + Px(62));
    ImGui::BeginGroup();
    ImGui::Dummy(ImVec2(1, Px(9)));
    TextCol(COL_TEXT2, ("/ " + K("score_t").text).c_str(), 17.f, g_bold);
    ImGui::EndGroup();
    Row(T_ECO, "eco", w);
    Row(T_IDLESH, "idle", w);
    Row(T_CRUISE, "cruise", w);
    Row(T_HARSH, "harsh", w);
    Row(T_LUG, "lug", w);
    Row(T_COLDLOAD, "coldload", w);
    Row(T_HOURS, "hours", w);
    RowText(X(T_AVGLOAD), (K("avgload").text + " · " + K("avgrpm").text).c_str(), 'n', w);
    Row(T_SHIFTS, "shifts", w);
    Row(T_STARTS, "starts", w);
    Section(T_S_HEAT);
    Heatmap(w, 110);
}

static void PageKayit(float w) {
    Section(T_S_FAULTS);
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    if (g_sim.faults.empty()) TextCol(COL_GOOD, X(T_NOFAULT), 13.5f);
    for (auto& f : g_sim.faults) {
        TextCol(COL_CRIT_TXT, f.first.c_str(), 13.5f, g_bold);
        TextCol(COL_TEXT2, f.second.c_str(), 12.5f);
    }
    Section(T_S_EVENTS);
    for (auto& e : g_sim.events) {
        std::string line = e.time + "  " + e.text;
        TextCol(e.lvl == 'c' ? COL_CRIT_TXT : e.lvl == 'w' ? COL_WARN : COL_TEXT2, line.c_str(), 12.5f);
    }
    ImGui::PopTextWrapPos();
}

static void DrawDetailed(const ImVec2& disp) {
    float base = S;
    Slot slot;
    int key = 1 + g_prefs.page;
    BeginPanel("##ebk_detail", disp, 330, key, slot);
    float w = Px(330);
    if (!g_sim_alive || !g_sim.valid) { SimOffline(w); EndPanel(key, slot, base); return; }
    if (Waiting(w)) { EndPanel(key, slot, base); return; }
    Header(w);
    // sayfa göstergesi: başlık + noktalar
    ImGui::Dummy(ImVec2(1, Px(2)));
    float x0 = ImGui::GetCursorPosX();
    TextCol(0xffffff, X(PAGE_NAMES[g_prefs.page]), 14.5f, g_bold);
    char pg[16];
    snprintf(pg, sizeof(pg), "%d/%d", g_prefs.page + 1, PAGE_COUNT);
    TextRight(COL_MUTED, pg, 12.5f, g_font, x0 + w);
    ImVec2 p = ImGui::GetCursorScreenPos();
    for (int i = 0; i < PAGE_COUNT; i++) {
        float cx = p.x + Px(4) + i * Px(13);
        ImGui::GetWindowDrawList()->AddCircleFilled(ImVec2(cx, p.y + Px(4)), Px(i == g_prefs.page ? 3.6f : 2.6f),
                                                    i == g_prefs.page ? C(0xffffff) : C(0xffffff, 0.3f));
    }
    ImGui::Dummy(ImVec2(w, Px(9)));
    ImGui::Separator();
    switch (g_prefs.page) {
        case 0: PageGenel(w); break;
        case 1: PageMotor(w); break;
        case 2: PageYag(w); break;
        case 3: PageSogutma(w); break;
        case 4: PageAku(w); break;
        case 5: PageLastik(w); break;
        case 6: PageSurus(w); break;
        case 7: PageYolculuk(w); break;
        case 8: PagePlan(w); break;
        case 9: PageAnaliz(w); break;
        default: PageKayit(w); break;
    }
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + w);
    TextCol(COL_FOOT, KeyText(X(T_FOOT2)).c_str(), 11.5f);
    ImGui::PopTextWrapPos();
    ImGui::PopTextWrapPos();
    EndPanel(key, slot, base);
}

// ekranın üst ortasında uyarı şeridi: varsayılan olarak yalnızca kritik uyarılar
static std::unordered_map<std::string, DWORD> g_warn_seen;
static void DrawBanner(const ImVec2& disp, bool only_new_crit) {
    DWORD now = GetTickCount();
    std::vector<const Warn*> list;
    for (auto& wr : g_sim.warnings) {
        bool eligible = wr.lvl == 'c' || (wr.lvl == 'w' && g_sim.banner_warn);
        if (!eligible) continue;
        std::string key = wr.text.substr(0, 40);
        auto it = g_warn_seen.find(key);
        if (it == g_warn_seen.end()) {
            g_warn_seen[key] = now;
            // ikaz sesini simülatör çalar (markaya göre, her uyarıda bir kez; 1.9+): katman ayrıca ses çıkarmaz
            it = g_warn_seen.find(key);
        }
        if (only_new_crit && (wr.lvl != 'c' || now - it->second > 10000)) continue;
        if (wr.lvl == 'w' && now - it->second > 12000) continue;  // dikkat uyarıları şeritte kısa süre kalır
        list.push_back(&wr);
        if (list.size() >= 3) break;
    }
    for (auto it = g_warn_seen.begin(); it != g_warn_seen.end();) {
        bool present = false;
        for (auto& wr : g_sim.warnings) if (wr.text.compare(0, 40, it->first) == 0) { present = true; break; }
        it = present ? std::next(it) : g_warn_seen.erase(it);
    }
    if (list.empty()) return;
    float k = disp.y / 1080.f;
    float w = std::min(disp.x * 0.40f, 620 * k);
    ImGui::SetNextWindowPos(ImVec2(disp.x * 0.5f, 12 * k), ImGuiCond_Always, ImVec2(0.5f, 0));
    ImGui::SetNextWindowSize(ImVec2(w, 0));
    bool crit = list[0]->lvl == 'c';
    float pulse = crit ? 0.55f + 0.45f * (0.5f + 0.5f * std::sin(now / 160.f)) : 1.f;
    ImGui::PushStyleColor(ImGuiCol_Border, C(crit ? COL_CRIT : COL_WARN, crit ? pulse : 0.8f));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, Px(2));
    ImGui::Begin("##ebk_banner", nullptr, OVL_FLAGS);
    ImGui::PushTextWrapPos(w - Px(12));
    for (auto* wr : list) {
        uint32_t col = wr->lvl == 'c' ? COL_CRIT_TXT : COL_WARN;
        TextCol(col, X(wr->lvl == 'c' ? T_CRIT : T_WARN), 12.f, g_bold);
        ImGui::SameLine(0, Px(8));
        TextCol(0xffffff, wr->text.c_str(), 14.5f, wr->lvl == 'c' ? g_bold : g_font);
    }
    ImGui::PopTextWrapPos();
    ImGui::End();
    ImGui::PopStyleVar();
    ImGui::PopStyleColor();
}

// ---------------------------------------------------------------- gösterge lambaları (alt orta)
// Oyunun gösterge panelindeki lambalar dışarıdan yakılamadığı için simülatörün ikazları burada gerçek kamyon
// göstergesindeki gibi lambalarla gösterilir. Simgeler çizgilerle çizilir (yazı tipinde bu simgeler yok).
static std::unordered_map<std::string, DWORD> g_lamp_since;  // lambanın yandığı an (yanıp sönme için)

// Yazıyı harflerin görünen kutusuna göre tam ortalar. CalcTextSize satır yüksekliğini (alt boşluk dahil) saydığı için
// onunla ortalanan büyük harfler (P, ABS, STOP) simgenin ortasından aşağıda kalırdı.
static void TextCentered(ImDrawList* dl, ImFont* font, float fs, ImVec2 c, ImU32 col, const char* txt) {
    ImFontBaked* baked = font->GetFontBaked(fs);
    float scale = fs / baked->Size, pen = 0.f;
    float x0 = FLT_MAX, x1 = -FLT_MAX, y0 = FLT_MAX, y1 = -FLT_MAX;
    for (const char* s = txt; *s; s++) {
        const ImFontGlyph* g = baked->FindGlyph((ImWchar)(unsigned char)*s);
        if (!g) continue;
        x0 = std::min(x0, pen + g->X0 * scale);
        x1 = std::max(x1, pen + g->X1 * scale);
        y0 = std::min(y0, g->Y0 * scale);
        y1 = std::max(y1, g->Y1 * scale);
        pen += g->AdvanceX * scale;
    }
    if (x0 > x1) return;
    dl->AddText(font, fs, ImVec2(std::round(c.x - (x0 + x1) * 0.5f), std::round(c.y - (y0 + y1) * 0.5f)), col, txt);
}

static void LampIcon(ImDrawList* dl, const std::string& id, ImVec2 c, float r, ImU32 col) {
    const float PI = 3.14159265f;
    float t = std::max(1.5f, std::round(r * 0.13f * 2.f) * 0.5f);
    auto P = [&](float x, float y) { return ImVec2(c.x + x * r, c.y + y * r); };
    auto Ln = [&](float x1, float y1, float x2, float y2, float th = 0.f) {
        dl->AddLine(P(x1, y1), P(x2, y2), col, th > 0 ? th : t);
    };
    auto Poly = [&](std::initializer_list<ImVec2> pts, bool closed) {
        std::vector<ImVec2> v;
        for (const auto& p : pts) v.push_back(P(p.x, p.y));
        dl->AddPolyline(v.data(), (int)v.size(), col, closed ? ImDrawFlags_Closed : ImDrawFlags_None, t);
    };
    if (id == "batt") {  // akü: gövde, kutup başları, - ve +
        dl->AddRect(P(-0.85f, -0.45f), P(0.85f, 0.6f), col, r * 0.08f, 0, t);
        dl->AddRectFilled(P(-0.62f, -0.68f), P(-0.3f, -0.45f), col);
        dl->AddRectFilled(P(0.3f, -0.68f), P(0.62f, -0.45f), col);
        Ln(-0.62f, 0.08f, -0.26f, 0.08f);
        Ln(0.26f, 0.08f, 0.62f, 0.08f);
        Ln(0.44f, -0.1f, 0.44f, 0.26f);
    } else if (id == "oil") {  // yağdanlık ve damla
        Poly({{-0.6f, -0.1f}, {0.25f, -0.1f}, {0.85f, -0.42f}, {0.9f, -0.33f}, {0.36f, 0.06f}, {0.3f, 0.4f}, {-0.6f, 0.4f}}, true);
        dl->AddRectFilled(P(-0.34f, -0.27f), P(-0.04f, -0.1f), col);
        Ln(-0.19f, -0.27f, -0.19f, -0.42f);
        Ln(-0.42f, -0.42f, 0.04f, -0.42f);
        Poly({{-0.6f, -0.02f}, {-0.9f, -0.2f}, {-0.9f, 0.16f}, {-0.6f, 0.3f}}, false);
        dl->AddTriangleFilled(P(0.88f, -0.16f), P(0.8f, 0.02f), P(0.96f, 0.02f), col);
        dl->AddCircleFilled(P(0.88f, 0.06f), r * 0.085f, col);
    } else if (id == "cool") {  // dalgaların içinde termometre
        Ln(0, -0.85f, 0, 0.18f, t * 1.25f);
        dl->AddCircleFilled(P(0, 0.3f), r * 0.18f, col);
        for (float y : {-0.7f, -0.45f, -0.2f}) Ln(0.08f, y, 0.36f, y);
        for (float y0 : {0.62f, 0.84f}) {
            ImVec2 pts[17];
            for (int i = 0; i <= 16; i++) {
                float u = i / 16.f;
                pts[i] = P(-0.9f + 1.8f * u, y0 + 0.07f * std::sin(u * 4 * PI));
            }
            dl->AddPolyline(pts, 17, col, ImDrawFlags_None, t);
        }
    } else if (id == "brake") {  // fren: daire, iki yay ve ünlem
        dl->AddCircle(c, r * 0.55f, col, 0, t);
        dl->PathArcTo(c, r * 0.82f, PI * 0.72f, PI * 1.28f);
        dl->PathStroke(col, ImDrawFlags_None, t);
        dl->PathArcTo(c, r * 0.82f, -PI * 0.28f, PI * 0.28f);
        dl->PathStroke(col, ImDrawFlags_None, t);
        Ln(0, -0.32f, 0, 0.1f, t * 1.2f);
        dl->AddCircleFilled(P(0, 0.27f), r * 0.075f, col);
    } else if (id == "eng") {  // motor arıza lambası (motor bloğu silueti)
        Poly({{-0.46f, -0.25f}, {-0.16f, -0.25f}, {-0.16f, -0.42f}, {-0.36f, -0.42f}, {-0.36f, -0.56f}, {0.39f, -0.56f},
              {0.39f, -0.42f}, {0.19f, -0.42f}, {0.19f, -0.25f}, {0.54f, -0.25f}, {0.54f, -0.05f}, {0.74f, -0.2f},
              {0.74f, 0.45f}, {0.54f, 0.3f}, {0.54f, 0.5f}, {-0.46f, 0.5f}, {-0.46f, 0.25f}, {-0.74f, 0.25f},
              {-0.74f, -0.05f}, {-0.46f, -0.05f}}, true);
    } else if (id == "dpf") {  // partikül filtresi: delikli gövde, giriş ve çıkış
        dl->AddRect(P(-0.62f, -0.42f), P(0.62f, 0.42f), col, r * 0.12f, 0, t);
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 2; j++) dl->AddCircleFilled(P(-0.3f + 0.3f * i, -0.14f + 0.28f * j), r * 0.075f, col);
        Ln(-0.95f, 0, -0.62f, 0);
        Ln(0.62f, 0, 0.95f, 0);
    } else if (id == "frost") {  // kar tanesi
        for (int k = 0; k < 6; k++) {
            float a = -PI / 2 + k * PI / 3, dx = std::cos(a), dy = std::sin(a);
            Ln(0, 0, dx * 0.85f, dy * 0.85f);
            for (float s : {-1.f, 1.f}) {
                float b = a + s * PI / 4;
                Ln(dx * 0.5f, dy * 0.5f, dx * 0.5f + std::cos(b) * 0.27f, dy * 0.5f + std::sin(b) * 0.27f);
            }
        }
    } else if (id == "svc") {  // anahtar (bakım zamanı)
        Ln(-0.68f, 0.68f, 0.17f, -0.17f, t * 2.2f);
        dl->AddCircleFilled(P(-0.68f, 0.68f), t * 1.1f, col);
        float open = -PI / 4;  // ağız sağ üste bakar
        dl->PathArcTo(P(0.38f, -0.38f), r * 0.3f, open + 0.75f, open + 2 * PI - 0.75f);
        dl->PathStroke(col, ImDrawFlags_None, t * 1.9f);
    } else if (id == "tire") {  // lastik basınç izleme (TPMS): üstü açık lastik kesiti, dişler ve ünlem
        float rr = 0.72f, cy = -0.08f;
        dl->PathArcTo(P(0, cy), r * rr, -0.16f * PI, 1.16f * PI);
        dl->PathStroke(col, ImDrawFlags_None, t * 1.15f);
        for (float x : {-0.5f, -0.17f, 0.17f, 0.5f}) {
            float y = cy + std::sqrt(rr * rr - x * x);
            Ln(x, y, x, y + 0.18f);
        }
        Ln(0, -0.42f, 0, 0.1f, t * 1.2f);
        dl->AddCircleFilled(P(0, 0.3f), r * 0.075f, col);
    } else if (id == "glow") {  // ön ısıtma (kızdırma bujisi): yan yana halkalardan spiral ve iki uç
        for (int i = 0; i < 4; i++)
            dl->AddEllipse(P(-0.42f + 0.28f * i, 0.0f), ImVec2(r * 0.2f, r * 0.42f), col, 0.0f, 0, t);
        Ln(-0.9f, 0.0f, -0.62f, 0.0f);
        Ln(0.62f, 0.0f, 0.9f, 0.0f);
    } else if (id == "fuel") {  // yakıt pompası
        dl->AddRect(P(-0.62f, -0.72f), P(0.18f, 0.72f), col, r * 0.06f, 0, t);
        dl->AddRectFilled(P(-0.46f, -0.56f), P(0.02f, -0.16f), col);
        Ln(-0.8f, 0.74f, 0.36f, 0.74f);
        Poly({{0.18f, -0.22f}, {0.44f, -0.22f}, {0.44f, 0.34f}, {0.62f, 0.34f}, {0.62f, -0.38f}, {0.46f, -0.56f}}, false);
    } else if (id == "adblue") {  // AdBlue damlası ve içinde sıvı dalgası
        dl->PathLineTo(P(0, -0.86f));
        dl->PathArcTo(P(0, 0.24f), r * 0.5f, -0.2f * PI, 1.2f * PI);
        dl->PathStroke(col, ImDrawFlags_Closed, t);
        ImVec2 pts[9];
        for (int i = 0; i <= 8; i++) {
            float u = i / 8.f;
            pts[i] = P(-0.3f + 0.6f * u, 0.28f + 0.06f * std::sin(u * 2 * PI));
        }
        dl->AddPolyline(pts, 9, col, ImDrawFlags_None, t);
    } else if (id == "gear") {  // şanzıman: dişli çark ve içinde ünlem
        dl->AddCircle(c, r * 0.58f, col, 0, t);
        for (int k = 0; k < 8; k++) {
            float a = k * PI / 4 + PI / 8, dx = std::cos(a), dy = std::sin(a);
            Ln(dx * 0.58f, dy * 0.58f, dx * 0.86f, dy * 0.86f, t * 2.4f);
        }
        Ln(0, -0.3f, 0, 0.07f, t * 1.2f);
        dl->AddCircleFilled(P(0, 0.25f), r * 0.075f, col);
    } else if (id == "steer") {  // direksiyon: simit, göbek, üç kol ve yanında ünlem
        const float cx = -0.14f, rr = 0.66f;
        dl->AddCircle(P(cx, 0), r * rr, col, 0, t);
        // kollar göbeğin ortasından simide kesintisiz uzanır, göbek üstlerine çizilir: birleşim yerlerinde boşluk kalmaz
        Ln(cx - rr, 0, cx + rr, 0);
        Ln(cx, 0, cx, rr);
        dl->AddCircleFilled(P(cx, 0), r * 0.15f, col);
        Ln(0.86f, -0.5f, 0.86f, 0.14f, t * 1.2f);
        dl->AddCircleFilled(P(0.86f, 0.34f), r * 0.075f, col);
    } else if (id == "abs" || id == "park") {  // ABS ve park freni: daire, iki yay, içinde "ABS" / "P"
        dl->AddCircle(c, r * 0.6f, col, 0, t);
        dl->PathArcTo(c, r * 0.84f, PI * 0.72f, PI * 1.28f);
        dl->PathStroke(col, ImDrawFlags_None, t);
        dl->PathArcTo(c, r * 0.84f, -PI * 0.28f, PI * 0.28f);
        dl->PathStroke(col, ImDrawFlags_None, t);
        TextCentered(dl, g_bold, std::round(r * (id == "abs" ? 0.5f : 0.9f)), c, col, id == "abs" ? "ABS" : "P");
    } else if (id == "start") {  // marş sistemi: anahtar (baş halkası, sap ve iki diş)
        dl->AddCircle(P(-0.5f, 0), r * 0.3f, col, 0, t);
        Ln(-0.2f, 0, 0.88f, 0, t * 1.3f);
        Ln(0.56f, 0, 0.56f, 0.26f, t * 1.3f);
        Ln(0.78f, 0, 0.78f, 0.2f, t * 1.3f);
    } else if (id == "stop") {  // kırmızı STOP yazısı
        TextCentered(dl, g_bold, std::round(r * 1.25f), c, col, "STOP");
    } else {
        dl->AddCircle(c, r * 0.7f, col, 0, t);
    }
}

static void DrawTelltales(const ImVec2& disp) {
    DWORD now = GetTickCount();
    // düzenlemede hiç lamba yanmıyorsa şeridin yeri ve boyutu örnek lambalarla gösterilir
    std::vector<SimState::Lamp> sample;
    bool demo = g_edit && g_sim.lamps.empty();
    if (demo) sample = {{"batt", 'w', X(T_SAMPLE_BATT)}, {"oil", 'c', X(T_SAMPLE_OIL)}, {"tire", 'w', X(T_SAMPLE_TIRE)}};
    const auto& v = demo ? sample : g_sim.lamps;
    if (!demo) {
        for (auto it = g_lamp_since.begin(); it != g_lamp_since.end();) {
            bool present = false;
            for (const auto& l : v) if (l.id == it->first) { present = true; break; }
            it = present ? std::next(it) : g_lamp_since.erase(it);
        }
    }
    if (v.empty()) return;
    float base_s = S;
    S = std::max(1.f, disp.y / 1080.f) * g_prefs.lamp_zoom;
    float k = disp.y / 1080.f;
    float icon = std::round(Px(34)), r = icon * 0.5f, gap = Px(6), lab = FS(11.5f);
    std::vector<float> widths;
    float total = 0;
    for (const auto& l : v) {
        float w = std::max(Px(46), g_bold->CalcTextSizeA(lab, FLT_MAX, 0.f, l.label.c_str()).x + Px(10));
        widths.push_back(w);
        total += w;
    }
    total += gap * (float)(v.size() - 1);
    ImVec2 lp(std::round(disp.x * 0.5f), std::round(disp.y - 16 * k));
    if (g_prefs.lamp_free) {  // fareyle taşınmış (alt orta noktası); şerit ekranda kalır
        float m = 16 * k, hw = std::max(0.f, (g_lamp_b.x - g_lamp_a.x) * 0.5f);   // önceki karenin boyutu
        float h = std::max(0.f, g_lamp_b.y - g_lamp_a.y);
        lp.x = std::round(Clampf(g_prefs.lx * disp.x, m + hw, std::max(m + hw, disp.x - m - hw)));
        lp.y = std::round(Clampf(g_prefs.ly * disp.y, std::min(m + h, disp.y - m), disp.y - m));
    }
    ImGui::SetNextWindowPos(lp, ImGuiCond_Always, ImVec2(0.5f, 1.f));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(Px(10), Px(8)));
    ImGui::Begin("##ebk_lamps", nullptr, OVL_FLAGS | ImGuiWindowFlags_AlwaysAutoResize);
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 p = ImGui::GetCursorScreenPos();
    float x = p.x;
    for (size_t i = 0; i < v.size(); i++) {
        const auto& l = v[i];
        DWORD age = now - g_lamp_since.emplace(l.id, now).first->second;
        bool red = l.lvl == 'c';
        // STOP sürekli, yeni yanan kırmızı lambalar ilk 6 sn yanıp söner (400 ms yanık / 400 ms sönük)
        float a = (l.id == "stop" || (red && age < 6000)) && (now / 400) % 2 ? 0.22f : 1.f;
        if (demo) a = 0.6f;
        uint32_t rgb = red ? COL_CRIT_TXT : COL_LAMP_AMBER;
        float w = widths[i];
        LampIcon(dl, l.id, ImVec2(std::round(x + w * 0.5f), std::round(p.y + r)), r * 0.95f, C(rgb, a));
        ImVec2 ts = g_bold->CalcTextSizeA(lab, FLT_MAX, 0.f, l.label.c_str());
        dl->AddText(g_bold, lab, ImVec2(std::round(x + (w - ts.x) * 0.5f), std::round(p.y + icon + Px(5))),
                    C(rgb, std::max(a, 0.65f)), l.label.c_str());
        x += w + gap;
    }
    ImGui::Dummy(ImVec2(total, icon + Px(5) + lab));
    ImVec2 wp = ImGui::GetWindowPos(), ws = ImGui::GetWindowSize();
    g_lamp_a = wp;
    g_lamp_b = ImVec2(wp.x + ws.x, wp.y + ws.y);
    g_lamp_ok = true;
    ImGui::End();
    ImGui::PopStyleVar();
    S = base_s;
}

// ---------------------------------------------------------------- oyun içi servis menüsü (Alt+F8)
// Maddeler, fiyatlar ve "tır durmalı / motor kapalı" kontrolleri simülatörden gelir; seçilen işlemin komutu
// katman bloğuna yazılır, simülatör uygular ve sonucu "r" satırıyla geri bildirir.
static bool g_svc_open = false;
static std::string g_svc_sel;        // seçili maddenin anahtarı (liste yenilense de seçim korunur)
static std::string g_svc_confirm;    // onay bekleyen maddenin anahtarı
static DWORD g_svc_confirm_t = 0;
static uint32_t g_svc_sent = 0;      // gönderilen son komutun sırası
static DWORD g_svc_sent_t = 0;
static std::string g_svc_local;      // yerel bilgi (ör. kullanılamayan maddenin nedeni)
static DWORD g_svc_local_t = 0;
static int g_svc_force_apply = 0;    // yalnızca test: bu kadar kare sonra seçili maddeyi onaysız uygula

static int SvcIndex() {
    const auto& v = g_sim.svc;
    for (int i = 0; i < (int)v.size(); i++)
        if (v[i].flag != 'h' && v[i].key == g_svc_sel) return i;
    return -1;
}

static void SvcSelectFirst() {
    g_svc_sel.clear();
    for (const auto& s : g_sim.svc)
        if (s.flag != 'h') { g_svc_sel = s.key; return; }
}

static void SvcMove(int dir) {
    const auto& v = g_sim.svc;
    int n = (int)v.size(), i = SvcIndex();
    g_svc_confirm.clear();
    if (n == 0) return;
    if (i < 0) { SvcSelectFirst(); return; }
    for (int step = 1; step <= n; step++) {
        int j = ((i + dir * step) % n + n) % n;
        if (v[j].flag != 'h') { g_svc_sel = v[j].key; return; }
    }
}

static void SvcSend(const SimState::Svc& s) {
    if (!g_ovl || s.cmd.empty()) return;
    uint32_t next = g_ovl->svc_seq + 1;
    if (next == 0) next = 1;
    char buf[sizeof(OvlBlock::svc_cmd)] = {};
    strncpy(buf, s.cmd.c_str(), sizeof(buf) - 1);
    memcpy((void*)g_ovl->svc_cmd, buf, sizeof(buf));
    g_ovl->svc_tick = GetTickCount();
    MemoryBarrier();
    g_ovl->svc_seq = next;  // sıra en son yazılır: simülatör komutu yarım okumaz
    g_svc_sent = next;
    g_svc_sent_t = GetTickCount();
    Log("servis komutu: %s", buf);
}

static void SvcApply() {
    int i = SvcIndex();
    if (i < 0) return;
    const auto& s = g_sim.svc[i];
    DWORD now = GetTickCount();
    if (s.flag == 'd') {  // kullanılamaz: nedenini göster
        g_svc_local = s.detail;
        g_svc_local_t = now;
        return;
    }
    if (s.flag == 'c' && !(g_svc_confirm == s.key && now - g_svc_confirm_t < 5000)) {
        g_svc_confirm = s.key;  // pahalı/geri dönüşsüz işlem: ikinci basışta uygulanır
        g_svc_confirm_t = now;
        return;
    }
    g_svc_confirm.clear();
    SvcSend(s);
}

static void StatusIcon(bool ok, uint32_t col) {
    float d = Px(15);
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 c(p.x + d * 0.5f, p.y + d * 0.5f + Px(2));
    dl->AddCircleFilled(c, d * 0.5f, C(col));
    ImU32 ink = C(0x1a1a19);
    float k = d * 0.22f, t = Px(2.f);
    if (ok) {
        dl->AddLine(ImVec2(c.x - k * 1.2f, c.y), ImVec2(c.x - k * 0.2f, c.y + k), ink, t);
        dl->AddLine(ImVec2(c.x - k * 0.2f, c.y + k), ImVec2(c.x + k * 1.3f, c.y - k * 1.1f), ink, t);
    } else {
        dl->AddLine(ImVec2(c.x - k, c.y - k), ImVec2(c.x + k, c.y + k), ink, t);
        dl->AddLine(ImVec2(c.x + k, c.y - k), ImVec2(c.x - k, c.y + k), ink, t);
    }
    ImGui::Dummy(ImVec2(d, d));
    ImGui::SameLine(0, Px(6));
}

static void DrawService(const ImVec2& disp) {
    float base = S;
    Slot slot;
    g_fit[FIT_SERVICE] = 1.f;  // menü yazıları küçülmez; sığmazsa satır sayısı azalır
    BeginPanel("##ebk_service", disp, 340, FIT_SERVICE, slot);
    float w = Px(340);
    DWORD now = GetTickCount();
    float x0 = ImGui::GetCursorPosX();
    TextCol(0xffffff, X(T_SVC_TITLE), 15.5f, g_bold);
    if (g_sim_alive && g_sim.valid && !g_sim.svc.empty())
        TextRight(COL_MUTED, K("truck").text.c_str(), 12.5f, g_font, x0 + w);
    ImGui::PushTextWrapPos(x0 + w);
    if (!g_sim_alive || !g_sim.valid) {
        TextCol(COL_WARN, X(T_SVC_NOSIM), 13.f);
    } else if (g_sim.svc.empty()) {
        TextCol(COL_MUTED, X(T_SVC_EMPTY), 13.f);
    } else {
        const Item& hint = K("svc_hint");
        if (hint.text != "—") TextCol(LvlRGB(hint.lvl), hint.text.c_str(), 12.5f);
    }
    ImGui::PopTextWrapPos();
    ImGui::Dummy(ImVec2(1, Px(2)));

    const auto& v = g_sim.svc;
    if (g_sim_alive && !v.empty()) {
        if (SvcIndex() < 0) SvcSelectFirst();
        int sel = SvcIndex();
        if (g_svc_force_apply > 0 && --g_svc_force_apply == 0 && sel >= 0) SvcSend(v[sel]);
        // seçili madde görünür kalsın diye ekrana sığan kadar satırlık pencere
        const int max_rows = std::max(6, std::min(30, (int)((slot.maxh - Px(170)) / Px(27))));
        int n = (int)v.size(), start = 0;
        if (n > max_rows) start = std::max(0, std::min(n - max_rows, sel - max_rows / 2));
        int end = std::min(n, start + max_rows);
        if (start > 0 || end < n) TextCol(COL_FOOT, KeyText(X(T_SVC_MORE)).c_str(), 11.f);
        ImDrawList* dl = ImGui::GetWindowDrawList();
        for (int i = start; i < end; i++) {
            const auto& s = v[i];
            if (s.flag == 'h') {
                ImGui::Dummy(ImVec2(1, Px(3)));
                TextCol(COL_MUTED, s.label.c_str(), 12.f, g_bold);
                continue;
            }
            bool is_sel = i == sel, off = s.flag == 'd';
            bool confirming = g_svc_confirm == s.key && now - g_svc_confirm_t < 5000;
            std::string confirm = KeyText(X(T_SVC_CONFIRM));
            const char* detail = confirming ? confirm.c_str() : s.detail.c_str();
            uint32_t dcol = confirming ? COL_WARN : off ? COL_WARN : COL_MUTED;
            ImGui::PushFont(g_font, FS(13.5f));
            ImVec2 ls = ImGui::CalcTextSize(s.label.c_str());
            ImGui::PopFont();
            ImGui::PushFont(g_font, FS(12.f));
            ImVec2 ds = ImGui::CalcTextSize(detail);
            ImGui::PopFont();
            bool two_lines = *detail && ls.x + ds.x + Px(26) > w;
            float h = Px(two_lines ? 38.f : 23.f);
            ImVec2 p = ImGui::GetCursorScreenPos();
            if (is_sel) {
                dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), C(0xffffff, 0.11f), Px(5));
                dl->AddRectFilled(p, ImVec2(p.x + Px(3), p.y + h), C(confirming ? COL_WARN : COL_ACCENT), Px(2));
            }
            uint32_t lcol = off ? COL_FOOT : 0xffffff;
            dl->AddText(is_sel ? g_bold : g_font, FS(13.5f), ImVec2(p.x + Px(10), p.y + Px(3)), C(lcol), s.label.c_str());
            if (*detail) {
                ImVec2 dp = two_lines ? ImVec2(p.x + Px(10), p.y + Px(21)) : ImVec2(p.x + w - Px(8) - ds.x, p.y + Px(4.5f));
                dl->AddText(g_font, FS(12.f), dp, C(dcol), detail);
            }
            ImGui::Dummy(ImVec2(w, h));
        }
    }

    // sonuç / bilgi satırı
    ImGui::Dummy(ImVec2(1, Px(2)));
    ImGui::PushTextWrapPos(x0 + w);
    if (g_svc_sent && g_sim.res_seq == g_svc_sent && now - g_svc_sent_t < 15000) {
        uint32_t col = g_sim.res_ok ? COL_GOOD : COL_CRIT_TXT;
        StatusIcon(g_sim.res_ok, col);
        TextCol(col, g_sim.res_msg.c_str(), 13.5f, g_bold);
    } else if (g_svc_sent && now - g_svc_sent_t < 4000) {
        TextCol(COL_MUTED, X(T_SVC_SENT), 13.f);
    } else if (!g_svc_local.empty() && now - g_svc_local_t < 4000) {
        TextCol(COL_WARN, g_svc_local.c_str(), 13.f);
    }
    TextCol(COL_FOOT, KeyText(X(T_SVC_FOOT)).c_str(), 11.5f);
    ImGui::PopTextWrapPos();
    EndPanel(FIT_SERVICE, slot, base);
}


// sürüş modu değişince ekranın alt ortasında 2,5 sn büyük bildirim
static int g_dm_shown = -1;
static DWORD g_dm_toast_t = 0;
static void DrawDriveToast(const ImVec2& disp) {
    int dm = g_drive_mode.load();
    DWORD now = GetTickCount();
    if (dm != g_dm_shown) {
        if (g_dm_shown >= 0 && dm >= 1) g_dm_toast_t = now;   // açılıştaki ilk değer bildirilmez
        g_dm_shown = dm;
    }
    if (!g_dm_toast_t || now - g_dm_toast_t > 2500 || dm < 1 || dm > 3) return;
    float age = (now - g_dm_toast_t) / 2500.f, a = age > 0.8f ? (1.f - age) / 0.2f : 1.f;
    ImDrawList* dl = ImGui::GetForegroundDrawList();
    float k = std::max(1.f, disp.y / 1080.f);
    const char* name = DRIVE_NAMES[dm];
    const char* desc = X(dm == 1 ? T_DM_ECO : dm == 2 ? T_DM_COMFORT : T_DM_SPORT);
    const char* title = X(T_DM_TITLE);
    float f1 = std::round(13 * k), f2 = std::round(34 * k), f3 = std::round(14 * k);
    ImVec2 s1 = g_bold->CalcTextSizeA(f1, FLT_MAX, 0.f, title), s2 = g_bold->CalcTextSizeA(f2, FLT_MAX, 0.f, name);
    ImVec2 s3 = g_font->CalcTextSizeA(f3, FLT_MAX, 0.f, desc);
    float bw = std::max(std::max(s1.x, s2.x), s3.x) + 48 * k, bh = s1.y + s2.y + s3.y + 34 * k;
    ImVec2 b0(std::round((disp.x - bw) * 0.5f), std::round(disp.y * 0.56f));   // yolun üstü, gösterge panelinin üstünde
    uint32_t col = DriveRGB(dm);
    dl->AddRectFilled(b0, ImVec2(b0.x + bw, b0.y + bh), C(0x0b0b0b, 0.86f * a), 10 * k);
    dl->AddRect(b0, ImVec2(b0.x + bw, b0.y + bh), C(col, 0.95f * a), 10 * k, 0, 2.5f * k);
    float y = b0.y + 10 * k;
    dl->AddText(g_bold, f1, ImVec2(std::round(b0.x + (bw - s1.x) * 0.5f), y), C(COL_MUTED, a), title);
    y += s1.y + 4 * k;
    dl->AddText(g_bold, f2, ImVec2(std::round(b0.x + (bw - s2.x) * 0.5f), y), C(col, a), name);
    y += s2.y + 4 * k;
    dl->AddText(g_font, f3, ImVec2(std::round(b0.x + (bw - s3.x) * 0.5f), y), C(COL_TEXT2, a), desc);
}

// ---------------------------------------------------------------- fareyle düzenleme (Ctrl+Alt+F8)
// Sürüşte oyun fareyi kamera/direksiyon için kullanır ve imleci gizler. Düzenleme modunda fare girdisi alt düzey fare
// kancasıyla (WH_MOUSE_LL) oyuna ulaşmadan yakalanır: hareket katmanın kendi imlecini yürütür, kamera ve direksiyon
// dönmez, tıklamalar oyuna gitmez. Kanca yalnızca düzenleme açıkken kurulur ve yalnızca oyun penceresi öndeyken ve
// katman çizilirken fareyi tutar; oyun takılırsa (300 ms kare gelmezse) fare kendiliğinden serbest kalır.
static ImVec2 g_cur(0, 0);                          // katmanın imleci (arka tampon pikseli)
static std::atomic<int> g_m_dx{0}, g_m_dy{0}, g_m_wheel{0}, g_m_lpress{0}, g_m_rpress{0}, g_m_mpress{0};
static std::atomic<bool> g_m_ldown{false};
static std::atomic<bool> g_edit_block{false};
static std::atomic<DWORD> g_edit_beat{0};
static HANDLE g_mouse_thread = nullptr;
static DWORD g_mouse_tid = 0;
static DWORD g_edit_idle = 0;                       // son fare girdisi (2 dk dokunulmazsa mod kendiliğinden kapanır)
static bool g_edit_test = false;                    // yalnızca test: girdi betikten gelir, kanca kurulmaz
static std::vector<std::string> g_edit_script;
static size_t g_edit_step = 0;
static int g_edit_wait = 0;
enum { DRAG_NONE, DRAG_PANEL, DRAG_PANEL_SIZE, DRAG_LAMPS, DRAG_LAMPS_SIZE };
enum { HOT_NONE, HOT_PANEL, HOT_PANEL_GRIP, HOT_LAMPS, HOT_LAMPS_GRIP };
static int g_drag = DRAG_NONE, g_hot = HOT_NONE;
static ImVec2 g_drag_off, g_drag_anchor;
static float g_drag_zoom0 = 1.f, g_drag_d0 = 1.f;

static LRESULT CALLBACK MouseLL(int code, WPARAM wp, LPARAM lp) {
    // bırakma olayı yalnızca basması da yakalanmış tuş için yutulur (mod açılırken basılı tutulan tuş takılı kalmasın)
    static bool l_seen = false, r_seen = false, m_seen = false;
    if (code == HC_ACTION && g_edit_block.load() && GetTickCount() - g_edit_beat.load() < 300) {
        const auto* m = (const MSLLHOOKSTRUCT*)lp;
        switch (wp) {
            case WM_MOUSEMOVE: {
                POINT c;
                GetCursorPos(&c);
                g_m_dx += m->pt.x - c.x;
                g_m_dy += m->pt.y - c.y;
                return 1;
            }
            case WM_LBUTTONDOWN: l_seen = true; g_m_ldown = true; g_m_lpress++; return 1;
            case WM_LBUTTONUP: g_m_ldown = false; if (!l_seen) break; l_seen = false; return 1;
            case WM_RBUTTONDOWN: r_seen = true; g_m_rpress++; return 1;
            case WM_RBUTTONUP: if (!r_seen) break; r_seen = false; return 1;
            case WM_MBUTTONDOWN: m_seen = true; g_m_mpress++; return 1;
            case WM_MBUTTONUP: if (!m_seen) break; m_seen = false; return 1;
            case WM_MOUSEWHEEL: g_m_wheel += (short)HIWORD(m->mouseData); return 1;
            case WM_MOUSEHWHEEL: case WM_XBUTTONDOWN: case WM_XBUTTONUP: return 1;
        }
    } else if (code == HC_ACTION && wp == WM_LBUTTONUP) {
        g_m_ldown = false;
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}

static DWORD WINAPI MouseThread(LPVOID) {
    // kanca noktaları fiziksel piksel verir; imleç konumu da fiziksel okunsun (ekran ölçeği %125 vb. olsa da)
    using SetCtx = void*(WINAPI*)(void*);
    if (auto f = (SetCtx)(void*)GetProcAddress(GetModuleHandleW(L"user32.dll"), "SetThreadDpiAwarenessContext"))
        f((void*)(intptr_t)-4);   // DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    MSG msg;
    PeekMessageW(&msg, nullptr, WM_USER, WM_USER, PM_NOREMOVE);   // ileti kuyruğu oluşsun
    HHOOK h = SetWindowsHookExW(WH_MOUSE_LL, MouseLL, g_module, 0);
    if (!h) {
        Log("HATA: fare kancasi kurulamadi (%lu)", GetLastError());
        return 0;
    }
    Log("fareyle duzenleme acildi");
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {}
    UnhookWindowsHookEx(h);
    Log("fareyle duzenleme kapandi");
    return 0;
}

static void StartMouseHook() {
    if (g_mouse_thread || g_edit_test) return;
    g_mouse_thread = CreateThread(nullptr, 0, MouseThread, nullptr, 0, &g_mouse_tid);
}

static void StopMouseHook() {
    g_edit_block = false;
    if (!g_mouse_thread) return;
    for (int i = 0; i < 50; i++) {
        if (PostThreadMessageW(g_mouse_tid, WM_QUIT, 0, 0)) break;
        if (WaitForSingleObject(g_mouse_thread, 20) == WAIT_OBJECT_0) break;
    }
    WaitForSingleObject(g_mouse_thread, 1000);
    CloseHandle(g_mouse_thread);
    g_mouse_thread = nullptr;
}

static void EnterEdit() {
    if (g_edit) return;
    g_edit = true;
    g_drag = DRAG_NONE;
    g_m_dx = 0; g_m_dy = 0; g_m_wheel = 0; g_m_lpress = 0; g_m_rpress = 0; g_m_mpress = 0;
    g_m_ldown = false;
    if (g_panel_ok) g_cur = ImVec2((g_panel_a.x + g_panel_b.x) * 0.5f, (g_panel_a.y + g_panel_b.y) * 0.5f);
    else g_cur = ImVec2(g_bb_w * 0.5f, g_bb_h * 0.5f);
    g_edit_idle = GetTickCount();
    StartMouseHook();
}

static void ExitEdit() {
    if (!g_edit) return;
    g_edit = false;
    g_drag = DRAG_NONE;
    StopMouseHook();
    SavePrefs();
}

// yalnızca test (EBK_TEST_EDIT): "n:K" K kare bekle · "on" düzenlemeyi aç · "c:x,y" imleci koy · "m:dx,dy" hareket ·
// "d"/"u" sol tuş bas/bırak · "w:n" tekerlek · "mid" orta tık · "r" sağ tık · "cp"/"cl" imleç panel/lamba ortasına ·
// "gp"/"gl" imleç panel/lamba boyut tutamacına
static void RunEditScript() {
    if (g_edit_wait > 0) { g_edit_wait--; return; }
    if (g_edit_step >= g_edit_script.size()) return;
    std::string op = g_edit_script[g_edit_step++];
    float a = 0, b = 0;
    if (op.rfind("n:", 0) == 0) g_edit_wait = atoi(op.c_str() + 2);
    else if (op == "on") EnterEdit();
    else if (op.rfind("c:", 0) == 0 && sscanf(op.c_str() + 2, "%f,%f", &a, &b) == 2) g_cur = ImVec2(a, b);
    else if (op.rfind("m:", 0) == 0 && sscanf(op.c_str() + 2, "%f,%f", &a, &b) == 2) { g_m_dx += (int)a; g_m_dy += (int)b; }
    else if (op == "d") { g_m_ldown = true; g_m_lpress++; }
    else if (op == "u") g_m_ldown = false;
    else if (op.rfind("w:", 0) == 0) g_m_wheel += atoi(op.c_str() + 2) * WHEEL_DELTA;
    else if (op == "mid") g_m_mpress++;
    else if (op == "r") g_m_rpress++;
    else if (op == "cp") g_cur = ImVec2((g_panel_a.x + g_panel_b.x) * 0.5f, (g_panel_a.y + g_panel_b.y) * 0.5f);
    else if (op == "cl") g_cur = ImVec2((g_lamp_a.x + g_lamp_b.x) * 0.5f, (g_lamp_a.y + g_lamp_b.y) * 0.5f);
    else if (op == "gp") { int px, py; PanelPivot(px, py); g_cur = ImVec2(px ? g_panel_a.x : g_panel_b.x, py ? g_panel_a.y : g_panel_b.y); }
    else if (op == "gl") g_cur = ImVec2(g_lamp_b.x, g_lamp_a.y);
}

static bool InRect(const ImVec2& p, const ImVec2& a, const ImVec2& b) { return p.x >= a.x && p.x <= b.x && p.y >= a.y && p.y <= b.y; }
static float Dist(const ImVec2& a, const ImVec2& b) { return std::sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y)); }

static ImVec2 PanelAnchor() {
    int px, py;
    PanelPivot(px, py);
    return ImVec2(px ? g_panel_b.x : g_panel_a.x, py ? g_panel_b.y : g_panel_a.y);
}
static ImVec2 PanelGrip() {   // tutturma köşesinin karşısı: oradan çekince panel büyür
    int px, py;
    PanelPivot(px, py);
    return ImVec2(px ? g_panel_a.x : g_panel_b.x, py ? g_panel_a.y : g_panel_b.y);
}
static ImVec2 LampAnchor() { return ImVec2((g_lamp_a.x + g_lamp_b.x) * 0.5f, g_lamp_b.y); }
static ImVec2 LampGrip() { return ImVec2(g_lamp_b.x, g_lamp_a.y); }

// panelin yeni sol üst köşesinden serbest konum: ekranda kalır, kenarlara yapışır, tutturma köşesi bulunduğu yarıdan seçilir
static void SetPanelFromRect(ImVec2 tl, const ImVec2& sz, const ImVec2& disp) {
    float k = disp.y / 1080.f, m = 16 * k, snap = 24 * k;
    if (tl.x - m < snap) tl.x = m;
    if (disp.x - m - (tl.x + sz.x) < snap) tl.x = disp.x - m - sz.x;
    if (tl.y - m < snap) tl.y = m;
    if (disp.y - m - (tl.y + sz.y) < snap) tl.y = disp.y - m - sz.y;
    tl.x = Clampf(tl.x, m, std::max(m, disp.x - m - sz.x));
    tl.y = Clampf(tl.y, m, std::max(m, disp.y - m - sz.y));
    int px = tl.x + sz.x * 0.5f > disp.x * 0.5f, py = tl.y + sz.y * 0.5f > disp.y * 0.5f;
    g_prefs.free = true;
    g_prefs.fpx = px;
    g_prefs.fpy = py;
    g_prefs.fx = (tl.x + sz.x * px) / disp.x;
    g_prefs.fy = (tl.y + sz.y * py) / disp.y;
}

static void SetLampsFromPoint(ImVec2 bc, const ImVec2& disp) {   // alt orta nokta
    float k = disp.y / 1080.f, m = 16 * k, snap = 24 * k;
    float hw = (g_lamp_b.x - g_lamp_a.x) * 0.5f, h = g_lamp_b.y - g_lamp_a.y;
    if (std::fabs(bc.x - disp.x * 0.5f) < snap) bc.x = disp.x * 0.5f;   // ortaya yapışır
    if (disp.y - m - bc.y < snap) bc.y = disp.y - m;
    bc.x = Clampf(bc.x, m + hw, std::max(m + hw, disp.x - m - hw));
    bc.y = Clampf(bc.y, std::min(m + h, disp.y - m), disp.y - m);
    g_prefs.lamp_free = true;
    g_prefs.lx = bc.x / disp.x;
    g_prefs.ly = bc.y / disp.y;
}

static bool GameFocused() {
    HWND fg = GetForegroundWindow();
    return fg && (fg == g_hwnd || GetAncestor(fg, GA_ROOT) == GetAncestor(g_hwnd, GA_ROOT));
}

// her karede, çizimden önce: fare girdisini işler (önceki karenin dikdörtgenleriyle isabet), konum/boyutu günceller
static void EditFrame(const ImVec2& disp) {
    if (g_edit_test) RunEditScript();
    g_edit_block = g_edit && !g_edit_test && !g_game_paused && GameFocused();
    g_edit_beat = GetTickCount();
    if (!g_edit) return;
    int dx = g_m_dx.exchange(0), dy = g_m_dy.exchange(0), wheel = g_m_wheel.exchange(0);
    int lpress = g_m_lpress.exchange(0), rpress = g_m_rpress.exchange(0), mpress = g_m_mpress.exchange(0);
    bool ldown = g_m_ldown.load();
    DWORD now = GetTickCount();
    if (dx || dy || wheel || lpress || rpress || mpress || ldown) g_edit_idle = now;
    if (rpress || now - g_edit_idle > 120000) { ExitEdit(); return; }
    float k = std::max(1.f, disp.y / 1080.f), grip_r = 16 * k;
    g_cur.x = Clampf(g_cur.x + dx, 0.f, disp.x - 1);
    g_cur.y = Clampf(g_cur.y + dy, 0.f, disp.y - 1);
    const ImVec2 c = g_cur;
    g_hot = HOT_NONE;
    if (g_panel_ok && Dist(c, PanelGrip()) < grip_r) g_hot = HOT_PANEL_GRIP;
    else if (g_lamp_ok && Dist(c, LampGrip()) < grip_r) g_hot = HOT_LAMPS_GRIP;
    else if (g_lamp_ok && InRect(c, g_lamp_a, g_lamp_b)) g_hot = HOT_LAMPS;
    else if (g_panel_ok && InRect(c, g_panel_a, g_panel_b)) g_hot = HOT_PANEL;
    if (mpress) {  // orta tık: üzerindeki öğe varsayılan konum ve boyuta döner
        if (g_hot == HOT_LAMPS || g_hot == HOT_LAMPS_GRIP) { g_prefs.lamp_free = false; g_prefs.lamp_zoom = 1.f; }
        else if (g_hot != HOT_NONE) { g_prefs.free = false; g_prefs.zoom = 1.f; g_prefs.scale = 1; }
        for (auto& f : g_fit) f = 1.f;
        SavePrefs();
    }
    if (g_drag == DRAG_NONE && lpress) {
        switch (g_hot) {
            case HOT_PANEL_GRIP:
                g_drag = DRAG_PANEL_SIZE; g_drag_anchor = PanelAnchor(); g_drag_zoom0 = g_prefs.zoom;
                g_drag_d0 = std::max(Dist(c, g_drag_anchor), 20.f);
                break;
            case HOT_LAMPS_GRIP:
                g_drag = DRAG_LAMPS_SIZE; g_drag_anchor = LampAnchor(); g_drag_zoom0 = g_prefs.lamp_zoom;
                g_drag_d0 = std::max(Dist(c, g_drag_anchor), 20.f);
                break;
            case HOT_PANEL: g_drag = DRAG_PANEL; g_drag_off = ImVec2(c.x - g_panel_a.x, c.y - g_panel_a.y); break;
            case HOT_LAMPS: { ImVec2 a = LampAnchor(); g_drag = DRAG_LAMPS; g_drag_off = ImVec2(c.x - a.x, c.y - a.y); break; }
        }
    }
    switch (g_drag) {
        case DRAG_PANEL:
            SetPanelFromRect(ImVec2(c.x - g_drag_off.x, c.y - g_drag_off.y),
                             ImVec2(g_panel_b.x - g_panel_a.x, g_panel_b.y - g_panel_a.y), disp);
            break;
        case DRAG_PANEL_SIZE:
            g_prefs.zoom = Clampf(g_drag_zoom0 * Dist(c, g_drag_anchor) / g_drag_d0, ZOOM_MIN, ZOOM_MAX);
            for (auto& f : g_fit) f = 1.f;
            break;
        case DRAG_LAMPS: SetLampsFromPoint(ImVec2(c.x - g_drag_off.x, c.y - g_drag_off.y), disp); break;
        case DRAG_LAMPS_SIZE:
            g_prefs.lamp_zoom = Clampf(g_drag_zoom0 * Dist(c, g_drag_anchor) / g_drag_d0, ZOOM_MIN, ZOOM_MAX);
            break;
    }
    if (g_drag != DRAG_NONE && !ldown) {
        g_drag = DRAG_NONE;
        for (auto& f : g_fit) f = 1.f;
        SavePrefs();
    }
    if (wheel && g_drag == DRAG_NONE) {
        float step = 0.05f * wheel / (float)WHEEL_DELTA;
        if (g_hot == HOT_LAMPS || g_hot == HOT_LAMPS_GRIP) g_prefs.lamp_zoom = Clampf(g_prefs.lamp_zoom + step, ZOOM_MIN, ZOOM_MAX);
        else if (g_hot != HOT_NONE) {
            g_prefs.zoom = Clampf(g_prefs.zoom + step, ZOOM_MIN, ZOOM_MAX);
            for (auto& f : g_fit) f = 1.f;
        }
        SavePrefs();
    }
}

static const char* PctFmt() { return g_lang == 1 ? "%d%%" : g_lang == 2 ? "%d %%" : "%%%d"; }

// çizimden sonra: çerçeveler, tutamaçlar, boyut etiketi, ipucu kutusu ve imleç (en üstte)
static void DrawEditOverlay(const ImVec2& disp) {
    ImDrawList* dl = ImGui::GetForegroundDrawList();
    float k = std::max(1.f, disp.y / 1080.f);
    float fs = std::round(13.f * k);
    auto frame = [&](bool ok, const ImVec2& a, const ImVec2& b, const ImVec2& grip, bool hot, bool grip_hot,
                     const char* name, float zoom) {
        if (!ok) return;
        dl->AddRect(ImVec2(a.x - 2 * k, a.y - 2 * k), ImVec2(b.x + 2 * k, b.y + 2 * k), C(COL_ACCENT, hot ? 1.f : 0.7f),
                    9 * k, 0, hot ? 3 * k : 1.5f * k);
        dl->AddCircleFilled(grip, (grip_hot ? 9.f : 7.f) * k, C(grip_hot ? 0xffffff : COL_ACCENT));
        dl->AddCircle(grip, (grip_hot ? 9.f : 7.f) * k, C(0x000000, 0.6f), 0, 1.5f * k);
        char pct[16], buf[96];
        snprintf(pct, sizeof(pct), PctFmt(), (int)std::lround(zoom * 100));
        snprintf(buf, sizeof(buf), "%s · %s", name, pct);
        ImVec2 ts = g_bold->CalcTextSizeA(fs, FLT_MAX, 0.f, buf);
        ImVec2 tp(std::round(a.x), std::round(a.y - ts.y - 8 * k));
        if (tp.y < 2 * k) tp.y = std::round(b.y + 6 * k);
        dl->AddRectFilled(ImVec2(tp.x - 5 * k, tp.y - 2 * k), ImVec2(tp.x + ts.x + 5 * k, tp.y + ts.y + 2 * k), C(0x101010, 0.88f), 4 * k);
        dl->AddText(g_bold, fs, tp, C(0xffffff), buf);
    };
    bool dp = g_drag == DRAG_PANEL || g_drag == DRAG_PANEL_SIZE, dlm = g_drag == DRAG_LAMPS || g_drag == DRAG_LAMPS_SIZE;
    frame(g_panel_ok, g_panel_a, g_panel_b, PanelGrip(), dp || g_hot == HOT_PANEL || g_hot == HOT_PANEL_GRIP,
          g_drag == DRAG_PANEL_SIZE || g_hot == HOT_PANEL_GRIP, X(T_EDIT_PANEL), g_prefs.zoom);
    frame(g_lamp_ok, g_lamp_a, g_lamp_b, LampGrip(), dlm || g_hot == HOT_LAMPS || g_hot == HOT_LAMPS_GRIP,
          g_drag == DRAG_LAMPS_SIZE || g_hot == HOT_LAMPS_GRIP, X(T_EDIT_LAMPS), g_prefs.lamp_zoom);
    // ipucu kutusu: üst orta, uyarı şeridinin altında (şerit üst kenarda en fazla ~3 satır)
    const char* title = X(T_EDIT_TITLE);
    std::string hint_s = KeyText(X(T_EDIT_HINT));
    const char* hint = hint_s.c_str();
    float hs = std::round(12.5f * k), wrap = std::min(disp.x - 40 * k, 760 * k);
    ImVec2 t1 = g_bold->CalcTextSizeA(fs, FLT_MAX, 0.f, title);
    ImVec2 t2 = g_font->CalcTextSizeA(hs, FLT_MAX, wrap, hint);
    float bw = std::max(t1.x, t2.x) + 24 * k, bh = t1.y + t2.y + 22 * k;
    ImVec2 b0(std::round((disp.x - bw) * 0.5f), std::round(disp.y * 0.15f));
    dl->AddRectFilled(b0, ImVec2(b0.x + bw, b0.y + bh), C(0x0b0b0b, 0.9f), 8 * k);
    dl->AddRect(b0, ImVec2(b0.x + bw, b0.y + bh), C(COL_ACCENT, 0.9f), 8 * k, 0, 1.5f * k);
    dl->AddText(g_bold, fs, ImVec2(b0.x + 12 * k, b0.y + 8 * k), C(COL_ACCENT), title);
    dl->AddText(g_font, hs, ImVec2(b0.x + 12 * k, b0.y + 12 * k + t1.y), C(COL_TEXT2), hint, nullptr, wrap);
    // imleç: beyaz ok, siyah kenar
    ImVec2 c = g_cur;
    ImVec2 p0 = c, p1(c.x, c.y + 18 * k), p2(c.x + 12.5f * k, c.y + 12.5f * k);
    ImVec2 q0(c.x + 4.5f * k, c.y + 12 * k), q1(c.x + 8.5f * k, c.y + 21 * k);
    dl->AddLine(q0, q1, C(0x000000), 5.5f * k);
    dl->AddLine(q0, q1, C(0xffffff), 2.5f * k);
    dl->AddTriangleFilled(p0, p1, p2, C(0xffffff));
    dl->AddTriangle(p0, p1, p2, C(0x000000), 1.6f * k);
}

// ---------------------------------------------------------------- kısayollar
static bool g_key_prev[256] = {};
static bool KeyEdge(int vk) {
    bool down = (GetAsyncKeyState(vk) & 0x8000) != 0;
    bool edge = down && !g_key_prev[vk];
    g_key_prev[vk] = down;
    return edge;
}

static void HandleKeys() {
    bool focused = GameFocused();
    bool f8 = KeyEdge(g_ovl_vk);   // katmanın tuşu (varsayılan F8, Ayarlar'dan değiştirilebilir)
    bool hud = KeyEdge(g_hud_vk);
    bool esc = KeyEdge(VK_ESCAPE);
    if (!focused) return;
    if (g_edit && esc) { ExitEdit(); return; }   // Esc düzenlemeyi bitirir (oyun menüsü de açılır)
    // oyunun HUD tuşu (varsayılan F3): oyun haritayı/rota ekranını gizleyip gösterirken katman da onunla gelir/gider.
    // Menüde (oyun duraklatılmışken) oyun bu tuşa tepki vermediği için sayılmaz.
    if (hud && g_hud_sync && !g_game_paused) g_hud_hidden = !g_hud_hidden;
    if (!f8 || g_game_paused) return;  // menüdeyken katman gizli: F8 görünmeyen ayarları değiştirmesin
    bool shift = GetAsyncKeyState(VK_SHIFT) & 0x8000, ctrl = GetAsyncKeyState(VK_CONTROL) & 0x8000;
    bool alt = GetAsyncKeyState(VK_MENU) & 0x8000;
    if (alt && ctrl) {  // Ctrl+Alt+F8: fareyle taşıma ve boyutlandırma
        if (g_edit) ExitEdit(); else EnterEdit();
        return;
    }
    if (alt) {  // Alt+F8: servis menüsü aç/kapat
        g_svc_open = !g_svc_open;
        g_svc_confirm.clear();
        if (g_svc_open && SvcIndex() < 0) SvcSelectFirst();
        return;
    }
    if (g_svc_open) {  // menü açıkken F8 tuşları menüyü yönetir
        if (ctrl && !shift) SvcApply();
        else if (shift && !ctrl) SvcMove(-1);
        else if (!ctrl && !shift) SvcMove(1);
        return;
    }
    if (g_hud_hidden) {  // F8 katmanı her zaman geri getirir (HUD ile eşleşme bozulursa da düzelir)
        g_hud_hidden = false;
        return;
    }
    if (ctrl && shift) {  // hazır boyutlar (panel ve lambalar birlikte)
        g_prefs.scale = (g_prefs.scale + 1) % 4;
        g_prefs.zoom = g_prefs.lamp_zoom = SCALES[g_prefs.scale];
    } else if (ctrl) {    // hazır köşeler (fareyle verilen serbest konum bırakılır)
        g_prefs.corner = g_prefs.free ? g_prefs.corner : (g_prefs.corner + 1) % POS_COUNT;
        g_prefs.free = false;
    }
    else if (shift) { g_prefs.page = (g_prefs.page + 1) % PAGE_COUNT; g_prefs.mode = 2; }
    else g_prefs.mode = (g_prefs.mode + 1) % MODE_COUNT;
    for (auto& f : g_fit) f = 1.f;
    SavePrefs();
}

// ---------------------------------------------------------------- test için ekran yakalama (EBK_CAPTURE)
static void CaptureBackbuffer(IDXGISwapChain* sc) {
    ID3D11Texture2D* bb = nullptr;
    if (FAILED(sc->GetBuffer(0, __uuidof(ID3D11Texture2D), (void**)&bb))) return;
    D3D11_TEXTURE2D_DESC td;
    bb->GetDesc(&td);
    td.Usage = D3D11_USAGE_STAGING;
    td.BindFlags = 0;
    td.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    td.MiscFlags = 0;
    ID3D11Texture2D* st = nullptr;
    if (SUCCEEDED(g_dev->CreateTexture2D(&td, nullptr, &st))) {
        g_ctx->CopyResource(st, bb);
        D3D11_MAPPED_SUBRESOURCE m;
        if (SUCCEEDED(g_ctx->Map(st, 0, D3D11_MAP_READ, 0, &m))) {
            FILE* f = _wfopen(g_capture_path.c_str(), L"wb");
            if (f) {
                int w = td.Width, h = td.Height, row = w * 3, pad = (4 - row % 4) % 4;
                BITMAPFILEHEADER fh{};
                BITMAPINFOHEADER ih{};
                fh.bfType = 0x4D42;
                fh.bfOffBits = sizeof(fh) + sizeof(ih);
                fh.bfSize = fh.bfOffBits + (row + pad) * h;
                ih.biSize = sizeof(ih); ih.biWidth = w; ih.biHeight = h; ih.biPlanes = 1; ih.biBitCount = 24;
                fwrite(&fh, sizeof(fh), 1, f);
                fwrite(&ih, sizeof(ih), 1, f);
                bool bgra = td.Format == DXGI_FORMAT_B8G8R8A8_UNORM || td.Format == DXGI_FORMAT_B8G8R8A8_UNORM_SRGB;
                std::vector<uint8_t> line(row + pad, 0);
                for (int y = h - 1; y >= 0; y--) {
                    const uint8_t* src = (const uint8_t*)m.pData + y * m.RowPitch;
                    for (int x = 0; x < w; x++) {
                        const uint8_t* px = src + x * 4;
                        line[x * 3 + 0] = bgra ? px[0] : px[2];
                        line[x * 3 + 1] = px[1];
                        line[x * 3 + 2] = bgra ? px[2] : px[0];
                    }
                    fwrite(line.data(), 1, line.size(), f);
                }
                fclose(f);
            }
            g_ctx->Unmap(st, 0);
        }
        st->Release();
    }
    bb->Release();
}

// ---------------------------------------------------------------- kare çizimi
static void RenderOverlay(IDXGISwapChain* sc) {
    if (g_shutdown) return;
    if (!g_imgui) {
        if (!InitImGui(sc)) return;
    }
    if (sc != g_sc) {
        DXGI_SWAP_CHAIN_DESC d{};
        if (FAILED(sc->GetDesc(&d)) || d.OutputWindow != g_hwnd) return;  // başka bir swapchain (ör. araç penceresi)
        g_sc = sc;
        ReleaseRTV();
    }
    ID3D11Device* dev = nullptr;
    if (SUCCEEDED(sc->GetDevice(__uuidof(ID3D11Device), (void**)&dev)) && dev) {
        if (dev != g_dev) {  // oyun cihazı yeniden oluşturdu (grafik ayarı değişimi)
            ImGui_ImplDX11_Shutdown();
            ReleaseRTV();
            if (g_ctx) g_ctx->Release();
            if (g_dev) g_dev->Release();
            g_dev = dev;
            g_dev->AddRef();
            g_dev->GetImmediateContext(&g_ctx);
            ImGui_ImplDX11_Init(g_dev, g_ctx);
        }
        dev->Release();
    }
    if (!g_rtv && !CreateRTV(sc)) return;

    if (g_ovl) g_ovl->frames = g_ovl->frames + 1;
    PollState();
    HandleKeys();

    ImGui_ImplDX11_NewFrame();
    ImGui_ImplWin32_NewFrame();
    ImGuiIO& io = ImGui::GetIO();
    // Pencere istemci alanı DPI sanallaştırmasında (ör. %125 ölçek) arka tampondan küçük görünebilir;
    // katman oyunun çizdiği gerçek çözünürlüğe göre yerleşsin diye arka tampon boyutu kullanılır.
    if (g_bb_w > 0 && g_bb_h > 0) io.DisplaySize = ImVec2((float)g_bb_w, (float)g_bb_h);
    if (io.DisplaySize.x <= 0 || io.DisplaySize.y <= 0) {
        RECT rc{};
        GetClientRect(g_hwnd, &rc);
        io.DisplaySize = ImVec2((float)(rc.right - rc.left), (float)(rc.bottom - rc.top));
    }
    ImVec2 disp = io.DisplaySize;
    if (g_game_paused && g_edit) ExitEdit();   // menüye geçilince düzenleme biter (fare oyuna döner)
    EditFrame(disp);                           // fareyle taşıma/boyut: önceki karenin konumlarıyla
    g_panel_ok = g_lamp_ok = false;
    S = std::max(1.f, io.DisplaySize.y / 1080.f) * g_prefs.zoom;
    ImGui::NewFrame();
    ImGui::PushFont(g_font, FS(14.f));
    ImGui::GetStyle().WindowPadding = ImVec2(Px(12), Px(10));
    ImGui::GetStyle().ItemSpacing = ImVec2(Px(8), Px(3));
    // Oyun duraklatılınca (ana menü, Esc menüsü, harita, yükleme ekranı) katmanın tamamı geçici olarak gizlenir;
    // sürüşe dönünce aynı düzende geri gelir.
    if (!g_game_paused) {
        // düzenlemede panel ve lambalar (F8 ile kapalı ya da HUD gizli olsa da) görünür
        bool hud_hidden = g_hud_hidden && !g_edit;
        int mode = g_edit && g_prefs.mode == 0 ? 1 : g_prefs.mode;
        bool hidden = !g_svc_open && (mode == 0 || hud_hidden);  // gizliyken yalnızca yeni kritik uyarı kısa süre görünür
        if (g_svc_open) DrawService(disp);  // servis menüsü açıkken panelin yerini alır (HUD gizli olsa da)
        else if (!hud_hidden && mode == 1) DrawCompact(disp);
        else if (!hud_hidden && mode == 2) DrawDetailed(disp);
        if (g_sim_alive && g_sim.valid) {
            if (!hud_hidden) DrawTelltales(disp);  // lambalar katman kapalıyken (F8) de yanar, HUD ile gizlenir
            DrawBanner(disp, hidden);
        } else if (g_edit) {
            DrawTelltales(disp);
        }
        g_drive_mode = (int)ReadDriveParams().mode;   // başlık etiketi ve değişim bildirimi
        DrawDriveToast(disp);
        if (g_edit) DrawEditOverlay(disp);
    }
    ImGui::PopFont();
    ImGui::Render();

    ID3D11RenderTargetView* old_rtv[D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT] = {};
    ID3D11DepthStencilView* old_dsv = nullptr;
    g_ctx->OMGetRenderTargets(D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, old_rtv, &old_dsv);
    g_ctx->OMSetRenderTargets(1, &g_rtv, nullptr);
    ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
    g_ctx->OMSetRenderTargets(D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, old_rtv, old_dsv);
    for (auto* r : old_rtv) if (r) r->Release();
    if (old_dsv) old_dsv->Release();
    if (!g_hook_confirmed && ++g_ok_frames >= 300) {   // panel sorunsuz çiziliyor: sonraki açılışta da kurulsun
        g_hook_confirmed = true;
        WriteIniInt(L"hook_ok", 1);
    }

    if (g_capture_after >= 0 && --g_capture_after == 0) {
        CaptureBackbuffer(sc);
        g_capture_after = -1;
    }
}

static HRESULT STDMETHODCALLTYPE HkPresent(IDXGISwapChain* sc, UINT sync, UINT flags) {
    if (t_depth == 0 && !(flags & DXGI_PRESENT_TEST)) {
        t_depth++;
        RenderOverlay(sc);
        t_depth--;
    }
    t_depth++;
    HRESULT hr = oPresent(sc, sync, flags);
    t_depth--;
    return hr;
}

static HRESULT STDMETHODCALLTYPE HkPresent1(IDXGISwapChain1* sc, UINT sync, UINT flags, const DXGI_PRESENT_PARAMETERS* p) {
    if (t_depth == 0 && !(flags & DXGI_PRESENT_TEST)) {
        t_depth++;
        RenderOverlay(sc);
        t_depth--;
    }
    t_depth++;
    HRESULT hr = oPresent1(sc, sync, flags, p);
    t_depth--;
    return hr;
}

static HRESULT STDMETHODCALLTYPE HkResize(IDXGISwapChain* sc, UINT n, UINT w, UINT h, DXGI_FORMAT f, UINT fl) {
    if (sc == g_sc) ReleaseRTV();
    return oResize(sc, n, w, h, f, fl);
}

// ---------------------------------------------------------------- kanca kurulumu
static DWORD WINAPI HookThread(LPVOID) {
    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = DefWindowProcW;
    wc.hInstance = g_module;
    wc.lpszClassName = L"EBKDummyWnd";
    RegisterClassExW(&wc);
    HWND hwnd = CreateWindowExW(0, wc.lpszClassName, L"", WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, nullptr, nullptr, g_module, nullptr);
    DXGI_SWAP_CHAIN_DESC sd{};
    sd.BufferCount = 1;
    sd.BufferDesc.Width = 64;
    sd.BufferDesc.Height = 64;
    sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.OutputWindow = hwnd;
    sd.SampleDesc.Count = 1;
    sd.Windowed = TRUE;
    sd.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;
    IDXGISwapChain* sc = nullptr;
    ID3D11Device* dev = nullptr;
    ID3D11DeviceContext* ctx = nullptr;
    D3D_FEATURE_LEVEL fl;
    HRESULT hr = D3D11CreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION,
                                               &sd, &sc, &dev, &fl, &ctx);
    if (FAILED(hr))
        hr = D3D11CreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_WARP, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &sd, &sc,
                                           &dev, &fl, &ctx);
    if (FAILED(hr) || !sc) {
        Log("HATA: sahte DX11 cihazi olusturulamadi (0x%08lx)", (unsigned long)hr);
        DestroyWindow(hwnd);
        return 0;
    }
    void** vt = *(void***)sc;
    void* present = vt[8];
    void* resize = vt[13];
    void* present1 = nullptr;
    IDXGISwapChain1* sc1 = nullptr;
    if (SUCCEEDED(sc->QueryInterface(__uuidof(IDXGISwapChain1), (void**)&sc1)) && sc1) {
        present1 = (*(void***)sc1)[22];
        sc1->Release();
    }
    sc->Release();
    ctx->Release();
    dev->Release();
    DestroyWindow(hwnd);
    UnregisterClassW(wc.lpszClassName, g_module);

    if (g_shutdown) return 0;
    if (MH_Initialize() != MH_OK) { Log("HATA: MinHook baslatilamadi"); return 0; }
    bool ok = MH_CreateHook(present, (void*)&HkPresent, (void**)&oPresent) == MH_OK;
    ok = ok && MH_CreateHook(resize, (void*)&HkResize, (void**)&oResize) == MH_OK;
    if (present1) MH_CreateHook(present1, (void*)&HkPresent1, (void**)&oPresent1);
    if (!ok || MH_EnableHook(MH_ALL_HOOKS) != MH_OK) { Log("HATA: DXGI kancalari kurulamadi"); return 0; }
    g_hooked = true;
    SetFlag(FLAG_HOOKED, true);
    Log("DXGI kancalari kuruldu (Present%s)", present1 ? " + Present1" : "");
    return 0;
}

// ---------------------------------------------------------------- oyun içi panel kurulsun mu?
// Panel, oyunun Present çağrısına kanca atar. OptiScaler ve DLSS 5 eklentileri de aynı yere bağlanır; birlikte oyunun
// donduğu bildirildi (OptiScaler kendi kare üretiminde tanımadığı katmanları kapatır, bizimkini tanımaz). Otomatik
// ayarda bunlardan biri oyun klasöründeyse ya da önceki açılışta kanca kurulduktan sonra oyun düzgün kapanmadıysa
// (donma, çökme) panel bu açılışta kurulmaz. Giriş cihazı (sürüş modları, motor durdurma, lastik patlaması) her durumda
// çalışır. Ayarlar'da "Açık" seçilirse her açılışta kurulur, "Kapalı" seçilirse hiç kurulmaz.
static int FindInjector() {   // oyun klasöründe: 1 OptiScaler, 2 DLSS 5, 0 yok
    wchar_t exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
    if (!n || n >= MAX_PATH) return 0;
    std::wstring dir(exe, n);
    dir.resize(dir.find_last_of(L"\\/") + 1);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((dir + L"*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    int found = 0;
    do {
        std::wstring name = fd.cFileName;
        CharLowerBuffW(&name[0], (DWORD)name.size());
        if (name.find(L"optiscaler") != std::wstring::npos) found = 1;
        else if (name.find(L"dlss5") != std::wstring::npos || name.find(L"dlss_5") != std::wstring::npos) found = 2;
    } while (!found && FindNextFileW(h, &fd));
    FindClose(h);
    return found;
}

static uint32_t PanelSkip() {
    if (g_panel_mode == 2) return SKIP_USER;
    if (g_panel_mode == 1) return SKIP_NONE;
    if (int inj = FindInjector()) return SKIP_INJECTOR | (uint32_t)(inj << 8);
    std::wstring p = PrefsPath();
    if (!p.empty() && GetPrivateProfileIntW(L"overlay", L"hook_ok", 1, p.c_str()) == 0) return SKIP_CRASH;
    return SKIP_NONE;
}

static void StartOverlay() {
    static bool started = false;
    if (started) return;
    started = true;
    LoadPrefs();
    LoadLang();
    LoadKeyPanel();
    CreateOvlBlock();
    wchar_t cap[MAX_PATH];
    if (GetEnvironmentVariableW(L"EBK_CAPTURE", cap, MAX_PATH)) {
        g_capture_path = cap;
        g_capture_after = 45;
        wchar_t n[16];
        if (GetEnvironmentVariableW(L"EBK_CAPTURE_AFTER", n, 16)) g_capture_after = std::max(2, _wtoi(n));
    }
    // yalnızca test: servis menüsünü aç / bir maddeyi seç / otomatik uygula
    wchar_t v[64];
    if (GetEnvironmentVariableW(L"EBK_FORCE_SERVICE", v, 64)) g_svc_open = _wtoi(v) != 0;
    if (GetEnvironmentVariableW(L"EBK_FORCE_SVC_SEL", v, 64)) {
        char a[64];
        WideCharToMultiByte(CP_UTF8, 0, v, -1, a, sizeof(a), nullptr, nullptr);
        g_svc_sel = a;
    }
    if (GetEnvironmentVariableW(L"EBK_FORCE_SVC_APPLY", v, 64)) g_svc_force_apply = _wtoi(v);
    if (GetEnvironmentVariableW(L"EBK_TEST_DRIVE", v, 64)) {  // yalnızca test: "mod,üst,artış,hız,eğri"
        float a[5] = {0, 1, 0, 0, 1};
        if (swscanf(v, L"%f,%f,%f,%f,%f", &a[0], &a[1], &a[2], &a[3], &a[4]) >= 1) {
            g_drive_test = {(uint32_t)a[0], a[1], a[2], a[3], a[4]};
            g_drive_test_on = true;
        }
    }
    wchar_t ws[1024];
    if (GetEnvironmentVariableW(L"EBK_TEST_EDIT", ws, 1024)) {  // yalnızca test: fareyle düzenleme betiği (kanca kurulmaz)
        char a[1024];
        WideCharToMultiByte(CP_UTF8, 0, ws, -1, a, sizeof(a), nullptr, nullptr);
        g_edit_script = Split(a, ';');
        g_edit_test = true;
    }
    g_skip = PanelSkip();
    if (g_ovl) g_ovl->reserved = g_skip;
    if (g_skip) {
        static const char* const why[] = {"", "Ayarlar'da kapali", "oyun klasorunde OptiScaler / DLSS 5 var",
                                          "onceki acilista oyun duzgun kapanmadi"};
        Log("oyun ici panel kurulmadi: %s (surus modlari ve motor durdurma calisir)", why[g_skip & 0xff]);
        return;
    }
    WriteIniInt(L"hook_ok", 0);   // panel 300 kare sorunsuz çizilene ya da oyun düzgün kapanana kadar "denendi"
    g_hook_thread = CreateThread(nullptr, 0, HookThread, nullptr, 0, nullptr);
}

static void StopOverlay() {
    if (g_shutdown.exchange(true)) return;
    StopMouseHook();
    if (g_hook_thread) {
        WaitForSingleObject(g_hook_thread, 3000);
        CloseHandle(g_hook_thread);
        g_hook_thread = nullptr;
    }
    if (g_hooked) {
        if (!g_hook_confirmed) WriteIniInt(L"hook_ok", 1);   // oyun düzgün kapandı: donma yok
        MH_DisableHook(MH_ALL_HOOKS);
        MH_Uninitialize();
        g_hooked = false;
    }
    SetFlag(FLAG_HOOKED | FLAG_RENDERING, false);
}

// ---------------------------------------------------------------- SCS SDK girişleri
static SCSAPI_VOID OnPauseEvent(const scs_event_t event, const void* const, const scs_context_t) {
    g_game_paused = event == SCS_TELEMETRY_EVENT_paused;
}

DLLEXPORT SCSAPI_RESULT scs_telemetry_init(const scs_u32_t version, const scs_telemetry_init_params_t* const params) {
    if (SCS_GET_MAJOR_VERSION(version) != 1) return SCS_RESULT_unsupported;
    const auto* p = static_cast<const scs_telemetry_init_params_v100_t*>(params);
    g_log = p->common.log;
    Log("ETS2 Bakim katmani %s yuklendi (%s)", EBK_VERSION, p->common.game_name);
    if (p->register_for_event) {
        p->register_for_event(SCS_TELEMETRY_EVENT_paused, OnPauseEvent, nullptr);
        p->register_for_event(SCS_TELEMETRY_EVENT_started, OnPauseEvent, nullptr);
    }
    if (p->register_for_channel) {  // sürüş modları için (gaz girdisi, etkin gaz, hız, hız sabitleyici)
        const struct { const char* name; std::atomic<float>* dst; } ch[] = {
            {SCS_TELEMETRY_TRUCK_CHANNEL_input_throttle, &g_tl_input},
            {SCS_TELEMETRY_TRUCK_CHANNEL_effective_throttle, &g_tl_eff},
            {SCS_TELEMETRY_TRUCK_CHANNEL_speed, &g_tl_speed},
            {SCS_TELEMETRY_TRUCK_CHANNEL_cruise_control, &g_tl_cruise}};
        for (const auto& c : ch)
            p->register_for_channel(c.name, SCS_U32_NIL, SCS_VALUE_TYPE_float, SCS_TELEMETRY_CHANNEL_FLAG_none, OnChannelFloat, c.dst);
    }
    StartOverlay();
    return SCS_RESULT_ok;
}

DLLEXPORT SCSAPI_VOID scs_telemetry_shutdown(void) {
    StopOverlay();
    g_log = nullptr;
}

DLLEXPORT SCSAPI_RESULT scs_input_init(const scs_u32_t version, const scs_input_init_params_t* const params) {
    if (version != SCS_INPUT_VERSION_1_00) return SCS_RESULT_unsupported;
    const auto* p = static_cast<const scs_input_init_params_v100_t*>(params);
    if (!g_log) g_log = p->common.log;
    static scs_input_device_input_t inputs[INPUT_COUNT];
    static const char* const CMD_DISPLAY[CMD_COUNT] = {"Ignition off", "Engine start stop"};
    for (int i = 0; i < CMD_COUNT; i++) {
        inputs[i].name = CMD_NAMES[i];
        inputs[i].display_name = CMD_DISPLAY[i];
        inputs[i].value_type = SCS_VALUE_TYPE_bool;
    }
    inputs[CMD_COUNT].name = "abackward";           // fren ekseni (oyuncunun frenine eklenir)
    inputs[CMD_COUNT].display_name = "Brake drag";
    inputs[CMD_COUNT].value_type = SCS_VALUE_TYPE_float;
    inputs[CMD_COUNT + 1].name = "steering";        // direksiyon ekseni (oyuncunun direksiyonuna eklenir)
    inputs[CMD_COUNT + 1].display_name = "Steering pull";
    inputs[CMD_COUNT + 1].value_type = SCS_VALUE_TYPE_float;
    inputs[CMD_COUNT + 2].name = "aforward";        // gaz ekseni (sürüş modu: oyuncunun gazına eklenir / çıkarılır)
    inputs[CMD_COUNT + 2].display_name = "Drive mode throttle";
    inputs[CMD_COUNT + 2].value_type = SCS_VALUE_TYPE_float;
    scs_input_device_t dev{};
    dev.name = "ets2bakim";
    dev.display_name = "ETS2 Bakim";
    dev.type = SCS_INPUT_DEVICE_TYPE_semantical;
    dev.input_count = INPUT_COUNT;
    dev.inputs = inputs;
    dev.callback_context = nullptr;
    dev.input_active_callback = InputActive;
    dev.input_event_callback = InputEvent;
    if (p->register_device(&dev) != SCS_RESULT_ok) {
        Log("HATA: semantik giris cihazi kaydedilemedi");
        return SCS_RESULT_generic_error;
    }
    CreateOvlBlock();
    SetFlag(FLAG_INPUT_REG, true);
    Log("semantik giris cihazi kaydedildi (ignitionoff, engine, abackward, steering, aforward)");
    return SCS_RESULT_ok;
}

DLLEXPORT SCSAPI_VOID scs_input_shutdown(void) {
    SetFlag(FLAG_INPUT_REG | FLAG_INPUT_ACTIVE, false);
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
