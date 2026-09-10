# Physical price field deployment (Windows + iPhone)

This is a deliberately small **proof-of-concept field setup** for opportunistic
shelf-price samples. It exposes the local `grocery_data` service through an
ephemeral Cloudflare Quick Tunnel. It does not turn the laptop into a generally
available production service, and it does not change digital catalogue prices.

The server binds only to `127.0.0.1`. Cloudflare terminates HTTPS and forwards
to that loopback service. Field mode is fail-closed: both
`FIELD_MODE_ENABLED=true` and a non-empty `PHYSICAL_CHECK_ACCESS_TOKEN` are
required before either helper script proceeds. The scripts never print the
token or put it on a command line. The Safari login POST necessarily traverses
Cloudflare's TLS termination; the token is therefore suitable only as a
temporary PoC application secret and must be rotated after the visit.

## One-time Windows preparation

From PowerShell in the repository root, install `cloudflared`:

```powershell
winget install --id Cloudflare.cloudflared -e
cloudflared --version
```

Install the Python dependencies in `.venv` (preferred) or ensure Python 3.12
can import `uvicorn` and `grocery_data`. Keep the normal database and snapshot
settings in the repository's uncommitted `.env` file.

Generate a temporary, high-entropy token. This command prints it once so that
you can copy it into `.env`; do not paste it into chat, a URL, source control,
screenshots, or shell scripts:

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
[Convert]::ToBase64String($bytes)
```

Configure `.env`:

```dotenv
GROCERY_DATABASE_URL=sqlite+pysqlite:///./.lund_production_refresh_20260826_v2.sqlite
FIELD_MODE_ENABLED=true
PHYSICAL_CHECK_ACCESS_TOKEN=<paste the generated token here>
FIELD_SESSION_TTL_SECONDS=1800
FIELD_LOGIN_ATTEMPTS_PER_MINUTE=5
FIELD_WRITE_REQUESTS_PER_MINUTE=60
FIELD_PUBLIC_ORIGIN=
FIELD_TRUSTED_PROXY_CIDRS=127.0.0.0/8,::1/128
```

The database line above names the current verified Lund field database in this
workspace. Replace it with the newly promoted database after a future refresh;
the server script deliberately refuses an implicit legacy default. Keep the
public origin blank for a dynamic Quick Tunnel. Trusting only the loopback CIDRs
lets the application use the client chain inserted by the local `cloudflared`
process for per-IP login limiting; arbitrary non-loopback proxy headers remain
untrusted. The service compares the browser's HTTPS `Origin` with the ordinary
request `Host`, and Uvicorn's own proxy-header processing stays disabled. The
field token must contain at least 32 UTF-8 bytes;
it is an application secret, not a Cloudflare credential. Rotate it after the
visit.

## Start a field session

1. On the Windows computer, open PowerShell in the repository root. Start the
   local API in the first terminal:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start_field_server.ps1
   ```

   It runs `grocery_data.app.main:app` on `127.0.0.1:8010` in the foreground.
   Leave the terminal open. It intentionally refuses to reuse an already
   running server because that process might not have field mode enabled.

2. Open a second PowerShell in the repository root and start the Quick Tunnel:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start_field_tunnel.ps1
   ```

   If `cloudflared.exe` is installed outside `PATH`, pass its absolute path as
   `-CloudflaredPath C:\path\to\cloudflared.exe`. The path is used only to
   launch the executable; the access token is never a process argument.

   The script first requires field mode and a 32-byte token, verifies that the
   local login page is alive and that an anonymous field API call is rejected,
   checks `cloudflared`, and only then opens the tunnel. Field mode intentionally
   does not expose the broad `/health`, docs, catalogue, or admin routes.
   Before launching `cloudflared`, the script removes the application token
   from that child process's environment and restores the parent setting only
   after the tunnel exits.
   Copy the temporary `https://...trycloudflare.com` URL printed by
   `cloudflared`. The hostname changes on every run.

3. On the iPhone, open that HTTPS URL in Safari and first go to
   `/physical-check/scanner-test` (for example
   `https://...trycloudflare.com/physical-check/scanner-test`). Authenticate
   with the same temporary field token when prompted. Never append the token
   to the URL. A successful login is also the required origin/proxy smoke test:
   if it returns an origin error or does not establish the field session, stop
   the tunnel and investigate the reviewed proxy configuration. Do not weaken
   origin, cookie, or CSRF checks to make the Quick Tunnel work.

4. Run the five-product camera check described below. Then open
   `/physical-check`, select **Hemköp Lund Karhögstorg**, start a 20-item
   validation session and
   keep blind capture enabled. For each suggested item:

   - scan the barcode and confirm the exact product, or enter its GTIN;
   - enter the observed shelf/package or weight price yourself;
   - choose regular, sale, member, multibuy, weight, or unknown as appropriate;
   - record the promotion condition rather than flattening a multibuy price;
   - choose `NO_MATCH` when identity cannot be proven;
   - save and continue until the session is complete.

   Safari asks for camera permission only after **Skanna streckkod** is pressed.
   No camera image or video is stored or uploaded. If camera decoding is
   unavailable, manual GTIN entry remains the required fallback.
   Digital prices stay hidden until an observation is committed in blind mode.

5. Finish the session and optionally export its sanitized JSON or CSV report.
   The report remains sampled evidence and must say `sampled_only=true`; it
   never overwrites the linked digital snapshot.

6. Immediately after the visit, press **Ctrl+C** in the tunnel terminal, then
   stop the local server with **Ctrl+C**. Set `FIELD_MODE_ENABLED=false` and
   rotate or remove `PHYSICAL_CHECK_ACCESS_TOKEN` in `.env`.

## Verify the scanner on a real iPhone first

The protected diagnostics page is deliberately write-free with respect to
physical prices:

```text
https://<temporary-host>.trycloudflare.com/physical-check/scanner-test
```

It decodes locally and shows scanner provider, camera/resolution, raw barcode,
normalized GTIN, format and scan time. It never creates a
`PhysicalPriceObservation` and never displays or updates a product price.

1. Open the URL in an ordinary Safari tab and log in when prompted.
2. Press **Starta kameran** and allow camera access. Permission is not requested
   at page load.
3. Hold one normal grocery EAN barcode horizontally inside the wide guide until
   it is decoded. The camera stops automatically after a successful read.
4. Record success/failure, displayed scan time, barcode and format in your test
   notes. Press **Starta kameran** again for the next package.
5. Repeat for five different products, preferably including an EAN-13 and, when
   available, an EAN-8 or UPC-labelled product.
6. Use **Testa ett manuellt GTIN** once as well. It exercises the same central
   normalization and checksum validation without opening the camera.
7. Continue to `/physical-check`, choose **Hemköp Lund Karhögstorg**, and make
   one real blind shelf-price observation. Confirm that only product identity is
   shown before save and that digital price/difference appears only afterwards.

The diagnostics page may submit privacy-minimal scanner health counters to the
local backend: provider, barcode format, duration, outcome and a bounded failure
reason. It does **not** submit the decoded barcode, camera label, frame, photo,
video, user identity or browser fingerprint.

## Scanner providers and supported codes

The field UI depends on a small `BarcodeScanner` abstraction rather than on the
browser `BarcodeDetector` API directly:

- `zxing`: the bundled `@zxing/browser` fallback and the preferred camera
  implementation on iPhone/iPad. It scans locally from the live `<video>` feed.
- `native_barcode_detector`: tried on non-iOS browsers only when the browser
  reports all required retail formats; runtime failure falls back to ZXing.
- `manual`: always available when camera access or both camera decoders fail.

Camera decoding is restricted to the retail formats EAN-13, EAN-8, UPC-A and
UPC-E. The shared GTIN normalizer validates checksums; malformed reads remain in
the scanner instead of being accepted silently. A successful scan stops every
media track immediately. Tracks are also stopped on cancel, page navigation and
page close. Camera frames never leave the browser.

## Safari and home-screen behavior

Use an ordinary **Safari tab over the HTTPS tunnel** for the first field tests.
All iPhone browsers use Apple's WebKit camera stack, and installed/home-screen
web apps can have a separate or less predictable camera-permission lifecycle on
some iOS versions. Saving the page to the home screen is optional, not required
for this PoC. If the installed version cannot reopen the camera, return to the
same HTTPS URL in Safari and grant camera access there.

If permission was denied earlier, review the site's camera permission in
Safari's website settings (or the Safari camera permission in iOS Settings),
then reload the page. Do not open the HTTP loopback URL on the phone:
`getUserMedia` requires a secure HTTPS context. The laptop and phone do not need
to share Wi-Fi; the laptop, backend and tunnel do need to remain running.

## Slow or failed scans

- Wipe the rear camera lens and use even light; avoid glare directly on glossy
  packaging.
- Hold the EAN bars horizontally and let the whole wide barcode fill most of
  the rectangular guide. Start roughly 15–25 cm away, hold still, then move a
  little closer or farther so autofocus can settle.
- Do not crop off the quiet white margins on either side of the barcode.
- Close Camera or another app/tab that may already own the camera, then press
  **Starta kameran** again.
- If Safari reports no permission, allow camera access for the current tunnel
  host and reload it. A new Quick Tunnel hostname needs its own permission.
- If the page reports an invalid checksum, try the barcode again rather than
  accepting the malformed value.
- If no valid read appears after several seconds, cancel and use manual GTIN.
  Scanner failure never blocks the validation session.

The normal field UI has no camera-selector requirement. It asks for the rear
`environment` camera at a useful 1280×720 target and requests continuous focus
when the browser exposes that capability. It does not force zoom or persist a
device choice.

## Rebuild the browser scanner bundle

The version-locked source is in `frontend/barcode-scanner`; the committed browser
bundle is `grocery_data/app/static/physical-barcode-scanner.js`. Running field
mode does not require Node or a CDN because FastAPI serves that local bundle.
Only contributors changing scanner source need to rebuild it:

```powershell
Push-Location .\frontend\barcode-scanner
pnpm install --frozen-lockfile
pnpm run check
pnpm run build
Pop-Location
```

`pnpm run check` runs syntax checks plus the GTIN/provider/camera-cleanup unit
tests. `pnpm run build` uses the pinned esbuild version and overwrites the
committed static bundle. The bundle contains `@zxing/browser` and
`@zxing/library`; their versions and MIT notice are recorded in
`frontend/barcode-scanner/THIRD_PARTY_NOTICES.md`.

## Preflight and failure behavior

- The tunnel script refuses non-loopback origins, a missing/short token,
  disabled field mode, a missing login page, an authentication boundary that
  does not fail closed, or a missing `cloudflared` executable.
- Field mode deliberately withholds the broad health/admin surface. Review
  freshness before switching into field mode; an old shelf observation must
  remain linked to the digital snapshot that was current at capture time.
- The server and tunnel run in the foreground. Closing either terminal or
  pressing Ctrl+C ends that part of the path.
- Quick Tunnel URLs are public, random, ephemeral, have no availability SLA,
  and are intended only for short PoC sessions. Possession of the URL is not
  authentication; the application token remains mandatory.
- Do not open Windows firewall ports or bind Uvicorn to `0.0.0.0` for this
  workflow. Do not commit `.env`, tunnel logs, tokens, or field exports that
  have not been reviewed.

## Future production deployment

A stable deployment should use a **named Cloudflare Tunnel**, a controlled DNS
name, Cloudflare Access or another proper identity layer, managed secret
storage, service supervision, audit/retention policy, backups, and explicit
proxy-header trust. That is intentionally future work; these scripts always
start a Quick Tunnel and do not create or configure a named tunnel.
