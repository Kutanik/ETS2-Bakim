// Oyunun yerine geçen test uygulaması: DX11 penceresi açar, eklentiyi SCS SDK'sı gibi yükler,
// kareleri çizer ve semantik giriş olaylarını okur. Katmanı oyunu açmadan denemek için.
//   test_host.exe <dll yolu> [kare sayısı]
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <d3d11.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <algorithm>
#include <vector>
#include <string>
#include <map>

#include "scssdk_telemetry.h"
#include "scssdk_input.h"

static scs_input_device_t g_dev{};
static bool g_has_dev = false;

static SCSAPI_VOID HostLog(const scs_log_type_t type, const scs_string_t msg) {
    printf("[oyun log %d] %s\n", type, msg);
    fflush(stdout);
}
// Oyun gibi duraklatma/başlama olaylarını gönderebilmek için kayıtlı geri çağrılar saklanır.
static scs_telemetry_event_callback_t g_ev_cb[16] = {};
static scs_context_t g_ev_ctx[16] = {};
static SCSAPI_RESULT RegEvent(const scs_event_t e, const scs_telemetry_event_callback_t cb, const scs_context_t ctx) {
    if (e < 16) { g_ev_cb[e] = cb; g_ev_ctx[e] = ctx; }
    return SCS_RESULT_ok;
}
static void FireEvent(scs_event_t e) {
    if (e < 16 && g_ev_cb[e]) g_ev_cb[e](e, nullptr, g_ev_ctx[e]);
}
static int EnvInt(const char* name, int def) {
    const char* v = getenv(name);
    return v && *v ? atoi(v) : def;
}
static SCSAPI_RESULT UnregEvent(const scs_event_t) { return SCS_RESULT_ok; }
// Kanal geri çağrıları saklanır: sürüş modu testinde oyunun gaz telemetrisi taklit edilir.
struct ChanCb { scs_telemetry_channel_callback_t cb; scs_context_t ctx; };
static std::map<std::string, ChanCb> g_chan;
static SCSAPI_RESULT RegChannel(const scs_string_t name, const scs_u32_t, const scs_value_type_t, const scs_u32_t,
                                const scs_telemetry_channel_callback_t cb, const scs_context_t ctx) {
    g_chan[name] = {cb, ctx};
    return SCS_RESULT_ok;
}
static void FireChannel(const char* name, float v) {
    auto it = g_chan.find(name);
    if (it == g_chan.end()) return;
    scs_value_t val{};
    val.type = SCS_VALUE_TYPE_float;
    val.value_float.value = v;
    it->second.cb(name, SCS_U32_NIL, &val, it->second.ctx);
}
// "kare:değer,kare:değer,..." çizelgesinde bu kareye düşen değer
static float Schedule(const char* env, int frame, float def) {
    const char* s = getenv(env);
    if (!s || !*s) return def;
    float v = def;
    while (*s) {
        int f, n = 0;
        float x;
        if (sscanf(s, "%d:%f%n", &f, &x, &n) != 2) break;
        if (f <= frame) v = x;
        s += n;
        if (*s == ',') s++;
    }
    return v;
}
static SCSAPI_RESULT UnregChannel(const scs_string_t, const scs_u32_t, const scs_value_type_t) { return SCS_RESULT_ok; }
static SCSAPI_RESULT RegDevice(const scs_input_device_t* const d) {
    g_dev = *d;
    g_has_dev = true;
    printf("[test] giris cihazi: %s (%s), tip %u, %u giris, ilk giris '%s'\n", d->name, d->display_name, d->type,
           d->input_count, d->inputs[0].name);
    return SCS_RESULT_ok;
}

static LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM w, LPARAM l) { return DefWindowProcW(h, m, w, l); }

// 24 bit BMP'yi RGBA'ya çevirir (arka plan olarak gerçek oyun ekran görüntüsü kullanmak için)
static bool LoadBmp(const char* path, int& w, int& h, std::vector<uint8_t>& rgba) {
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    BITMAPFILEHEADER fh;
    BITMAPINFOHEADER ih;
    fread(&fh, sizeof(fh), 1, f);
    fread(&ih, sizeof(ih), 1, f);
    if (ih.biBitCount != 24) { fclose(f); return false; }
    w = ih.biWidth;
    h = abs(ih.biHeight);
    int row = (w * 3 + 3) & ~3;
    std::vector<uint8_t> raw((size_t)row * h);
    fseek(f, fh.bfOffBits, SEEK_SET);
    fread(raw.data(), 1, raw.size(), f);
    fclose(f);
    rgba.resize((size_t)w * h * 4);
    for (int y = 0; y < h; y++) {
        const uint8_t* src = raw.data() + (size_t)(ih.biHeight > 0 ? h - 1 - y : y) * row;
        for (int x = 0; x < w; x++) {
            uint8_t* d = &rgba[((size_t)y * w + x) * 4];
            d[0] = src[x * 3 + 2]; d[1] = src[x * 3 + 1]; d[2] = src[x * 3]; d[3] = 255;
        }
    }
    return true;
}

int main(int argc, char** argv) {
    if (argc < 2) { printf("kullanim: test_host <dll> [kare] [arka_plan.bmp]\n"); return 1; }
    int frames = argc > 2 ? atoi(argv[2]) : 120;
    int W = 1600, Hh = 900;
    std::vector<uint8_t> bg;
    if (argc > 3 && LoadBmp(argv[3], W, Hh, bg)) printf("[test] arka plan: %dx%d\n", W, Hh);
    HINSTANCE inst = GetModuleHandleW(nullptr);
    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WndProc;
    wc.hInstance = inst;
    wc.lpszClassName = L"EBKTestHost";
    RegisterClassExW(&wc);
    RECT r{0, 0, W, Hh};
    AdjustWindowRect(&r, WS_OVERLAPPEDWINDOW, FALSE);
    HWND hwnd = CreateWindowExW(0, wc.lpszClassName, L"ETS2 Bakim katman testi", WS_OVERLAPPEDWINDOW, 40, 40,
                                r.right - r.left, r.bottom - r.top, nullptr, nullptr, inst, nullptr);

    DXGI_SWAP_CHAIN_DESC sd{};
    sd.BufferCount = 2;
    sd.BufferDesc.Width = W;
    sd.BufferDesc.Height = Hh;
    sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.OutputWindow = hwnd;
    sd.SampleDesc.Count = 1;
    sd.Windowed = TRUE;
    sd.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    IDXGISwapChain* sc = nullptr;
    ID3D11Device* dev = nullptr;
    ID3D11DeviceContext* ctx = nullptr;
    HRESULT hr = D3D11CreateDeviceAndSwapChain(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION,
                                               &sd, &sc, &dev, nullptr, &ctx);
    if (FAILED(hr)) { printf("DX11 olusturulamadi 0x%08lx\n", (unsigned long)hr); return 1; }
    ID3D11Texture2D* bb = nullptr;
    sc->GetBuffer(0, __uuidof(ID3D11Texture2D), (void**)&bb);
    ID3D11RenderTargetView* rtv = nullptr;
    dev->CreateRenderTargetView(bb, nullptr, &rtv);
    ID3D11Texture2D* bgtex = nullptr;
    if (!bg.empty()) {
        D3D11_TEXTURE2D_DESC td;
        bb->GetDesc(&td);
        td.Usage = D3D11_USAGE_IMMUTABLE;
        td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
        td.CPUAccessFlags = 0;
        td.MiscFlags = 0;
        D3D11_SUBRESOURCE_DATA sdata{bg.data(), (UINT)(W * 4), 0};
        dev->CreateTexture2D(&td, &sdata, &bgtex);
    }

    HMODULE dll = LoadLibraryA(argv[1]);
    if (!dll) { printf("DLL yuklenemedi: %lu\n", GetLastError()); return 1; }
    auto tinit = (scs_result_t (*)(scs_u32_t, const scs_telemetry_init_params_t*))GetProcAddress(dll, "scs_telemetry_init");
    auto tshut = (void (*)())GetProcAddress(dll, "scs_telemetry_shutdown");
    auto iinit = (scs_result_t (*)(scs_u32_t, const scs_input_init_params_t*))GetProcAddress(dll, "scs_input_init");
    auto ishut = (void (*)())GetProcAddress(dll, "scs_input_shutdown");
    printf("[test] disa aktarimlar: telemetry_init=%p telemetry_shutdown=%p input_init=%p input_shutdown=%p\n",
           (void*)tinit, (void*)tshut, (void*)iinit, (void*)ishut);
    if (!tinit || !iinit) return 1;

    scs_telemetry_init_params_v100_t tp{};
    tp.common.game_name = "Euro Truck Simulator 2 (test)";
    tp.common.game_id = "eut2";
    tp.common.game_version = SCS_MAKE_VERSION(1, 18);
    tp.common.log = HostLog;
    tp.register_for_event = RegEvent;
    tp.unregister_from_event = UnregEvent;
    tp.register_for_channel = RegChannel;
    tp.unregister_from_channel = UnregChannel;
    printf("[test] telemetry_init -> %d\n", tinit(SCS_TELEMETRY_VERSION_1_01, &tp));
    // Oyun telemetriyi duraklatılmış başlatır, sürüş başlayınca "started" gönderir.
    // EBK_TEST_PAUSED=1: menüde kal · EBK_TEST_PAUSE_AT / EBK_TEST_RESUME_AT: o karede duraklat / devam et
    int pause_at = EnvInt("EBK_TEST_PAUSE_AT", -1), resume_at = EnvInt("EBK_TEST_RESUME_AT", -1);
    if (!EnvInt("EBK_TEST_PAUSED", 0)) FireEvent(SCS_TELEMETRY_EVENT_started);

    scs_input_init_params_v100_t ip{};
    ip.common = tp.common;
    ip.register_device = RegDevice;
    printf("[test] input_init -> %d\n", iinit(SCS_INPUT_VERSION_1_00, &ip));
    if (g_has_dev && g_dev.input_active_callback) g_dev.input_active_callback(1, g_dev.callback_context);

    Sleep(800);  // kanca iş parçacığı
    // EBK_TEST_HIDDEN=1: pencere ekran dışında ve odak almadan açılır (oyun / kayıt sürerken görüntü almak için)
    if (getenv("EBK_TEST_HIDDEN")) {
        SetWindowLongPtrW(hwnd, GWL_EXSTYLE, GetWindowLongPtrW(hwnd, GWL_EXSTYLE) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE);
        SetWindowPos(hwnd, HWND_BOTTOM, -20000, -20000, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE);
    }
    ShowWindow(hwnd, SW_SHOWNOACTIVATE);
    for (int i = 0; i < frames; i++) {
        MSG msg;
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
        if (i == pause_at) { FireEvent(SCS_TELEMETRY_EVENT_paused); printf("[test] kare %d: oyun duraklatildi\n", i); }
        if (i == resume_at) { FireEvent(SCS_TELEMETRY_EVENT_started); printf("[test] kare %d: oyun devam ediyor\n", i); }
        // "oyun sahnesi": gökyüzü/yol benzeri koyu degrade
        float t = i / 60.f;
        float clear[4] = {0.18f + 0.02f * sinf(t), 0.24f, 0.30f, 1.f};
        ctx->OMSetRenderTargets(1, &rtv, nullptr);
        if (bgtex) ctx->CopyResource(bb, bgtex);
        else ctx->ClearRenderTargetView(rtv, clear);
        // giriş cihazı olaylarını oku (oyunun ana döngüsü gibi: eklenti "olay yok" diyene kadar). Oyunda üst sınır yoktur;
        // burada 64 olaydan sonra durulur ve hata yazılır (eklenti bir karede bitmeyen olay üretirse oyun donar).
        static float aforward = 0.f;   // eklentinin gaza eklediği son değer
        static int thr_events = 0, thr_frame_events = 0;
        thr_frame_events = 0;
        if (g_has_dev) {
            scs_u32_t flags = SCS_INPUT_EVENT_CALLBACK_FLAG_first_in_frame;
            if (i == EnvInt("EBK_TEST_REACTIVATE_AT", -1)) {   // cihaz yeniden etkinleşti (odak dönüşü)
                flags |= SCS_INPUT_EVENT_CALLBACK_FLAG_first_after_activation;
                printf("[test] kare %d: cihaz yeniden etkin\n", i);
            }
            int n = 0;
            for (; n < 64; n++) {
                scs_input_event_t ev{};
                if (g_dev.input_event_callback(&ev, flags, g_dev.callback_context) != SCS_RESULT_ok) break;
                if (g_dev.inputs[ev.input_index].value_type == SCS_VALUE_TYPE_float) {
                    if (!strcmp(g_dev.inputs[ev.input_index].name, "aforward")) {
                        aforward = ev.value_float.value;
                        thr_events++;
                        thr_frame_events++;
                    }
                    else printf("[test] kare %d: eksen '%s' = %.3f\n", i, g_dev.inputs[ev.input_index].name, ev.value_float.value);
                }
                else
                    printf("[test] kare %d: giris olayi '%s' = %u\n", i, g_dev.inputs[ev.input_index].name, ev.value_bool.value);
                fflush(stdout);
                flags = 0;
            }
            if (n >= 64) printf("[test] HATA: kare %d: eklenti bir karede 64'ten fazla olay gonderdi (oyunda donma)\n", i);
        }
        // sürüş modu testi (EBK_TEST_THROTTLE): oyuncunun pedalı + eklentinin katkısı = oyunun gazı (0..1);
        // EBK_TEST_THR_MODEL=2 ise telemetrinin gaz girdisi eklentinin katkısını içermez.
        // EBK_TEST_THR_LAG=n: oyun eklentinin katkısını n kare geç uygular (telemetri de geç gösterir).
        // EBK_TEST_THR_NOISE=n: pedala ±n/10000 gürültü (gerçek pedal; basılıyken), bırakılıyken 0..n/20000.
        if (getenv("EBK_TEST_THROTTLE")) {
            static float af_hist[16] = {};
            static uint32_t rng = 12345u;
            int lag = std::max(0, std::min(15, EnvInt("EBK_TEST_THR_LAG", 0)));
            float noise = EnvInt("EBK_TEST_THR_NOISE", 0) / 10000.f;
            af_hist[i % 16] = aforward;
            float applied = i >= lag ? af_hist[(i - lag) % 16] : 0.f;
            float raw = Schedule("EBK_TEST_THROTTLE", i, 0.f), kmh = Schedule("EBK_TEST_SPEED", i, 60.f);
            if (noise > 0.f) {
                rng = rng * 1664525u + 1013904223u;
                float u = (rng >> 8) / 16777216.f;   // 0..1
                raw = raw > 0.f ? std::max(0.f, std::min(1.f, raw + noise * (2.f * u - 1.f))) : noise * 0.5f * u;
            }
            float cruise = Schedule("EBK_TEST_CRUISE", i, 0.f);
            float mixed = std::max(0.f, std::min(1.f, raw + applied));
            float input = EnvInt("EBK_TEST_THR_MODEL", 1) == 2 ? raw : mixed;
            float eff = cruise > 0 ? 0.6f : mixed;
            FireChannel("truck.input.throttle", input);
            FireChannel("truck.effective.throttle", eff);
            FireChannel("truck.speed", kmh / 3.6f);
            FireChannel("truck.cruise_control", cruise / 3.6f);
            printf("[thr] %d ham=%.4f girdi=%.6f etkin=%.6f katki=%.6f olay=%d toplam=%d\n", i, raw, input, eff, applied,
                   thr_frame_events, thr_events);
            fflush(stdout);
        }
        sc->Present(1, 0);
    }
    if (ishut) ishut();
    if (tshut) tshut();
    printf("[test] bitti\n");
    if (bgtex) bgtex->Release();
    bb->Release();
    rtv->Release();
    sc->Release();
    ctx->Release();
    dev->Release();
    DestroyWindow(hwnd);
    return 0;
}
