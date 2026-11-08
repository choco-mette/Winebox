# Sandbox Specification

Dokumen ini mendefinisikan spesifikasi teknis eksekusi Bubblewrap (`bwrap`) di WineBox.

## 1. Baseline Flag Bubblewrap

Setiap sandbox WineBox dijalankan menggunakan argumen dasar berikut:

```bash
bwrap \
  --unshare-user \
  --unshare-ipc \
  --unshare-pid \
  --unshare-uts \
  --unshare-cgroup \
  --die-with-parent \
  --new-session \
  --proc /proc \
  --dev /dev \
  --tmpfs /tmp \
  --tmpfs /run \
  --ro-bind /usr /usr \
  --ro-bind-try /lib /lib \
  --ro-bind-try /lib64 /lib64 \
  --ro-bind-try /bin /bin \
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache \
  --ro-bind-try /etc/ld.so.conf /etc/ld.so.conf \
  --ro-bind-try /etc/ld.so.conf.d /etc/ld.so.conf.d \
  --ro-bind-try /etc/resolv.conf /etc/resolv.conf \
  --ro-bind-try /etc/hosts /etc/hosts \
  --ro-bind-try /etc/nsswitch.conf /etc/nsswitch.conf
```

---

## 2. Mount Lingkungan Prefix & Home

Setiap Wine Prefix memiliki virtual HOME privat dan direktori prefix yang di-bind ke dalam sandbox:

```bash
  # Mount WINEPREFIX
  --bind <prefix_dir>/prefix <sandbox_prefix_path> \
  # Mount Isolated HOME
  --bind <prefix_dir>/home /home/<user> \
  --setenv HOME /home/<user> \
  --setenv WINEPREFIX <sandbox_prefix_path>
```

---

## 3. Dynamic Hardware & Network Passthrough

Argumen ditambahkan secara kondisional oleh `MountBuilder` berdasarkan objek `SecurityPolicy`:

### 3.1 Display (`policy.display == True`)
- Socket X11: `--ro-bind-try /tmp/.X11-unix /tmp/.X11-unix`
- XAuthority: `--ro-bind-try <xauthority_file> <sandbox_xauth>` + `--setenv XAUTHORITY <sandbox_xauth>`
- Environment: `--setenv DISPLAY <host_display>`

### 3.2 Audio (`policy.audio == True`)
- Socket PulseAudio/PipeWire:
  `--ro-bind-try /run/user/<uid>/pulse /run/user/<uid>/pulse` atau
  `--ro-bind-try /run/user/<uid>/pipewire-0 /run/user/<uid>/pipewire-0`
- Environment: `--setenv PULSE_SERVER unix:/run/user/<uid>/pulse/native`

### 3.3 GPU (`policy.gpu == True`)
- Direct Rendering Infrastructure: `--dev-bind-try /dev/dri /dev/dri`
- NVIDIA Passthrough (jika terdeteksi):
  `--dev-bind-try /dev/nvidiactl /dev/nvidiactl`, `--dev-bind-try /dev/nvidia0 /dev/nvidia0`

### 3.4 Jaringan
- `policy.network == True`: tambahkan `--share-net`
- `policy.network == False`: tambahkan `--unshare-net` (hanya loopback `lo`)

---

## 4. Validasi Pre-flight (Fail-Fast)

Sebelum mengeksekusi container aplikasi, `BwrapAdapter` menjalankan uji dummy:
```bash
bwrap --unshare-user --ro-bind / / true
```
Jika return code != 0 (misalnya akibat unprivileged user namespace dinonaktifkan di level kernel), eksekusi dibatalkan seketika dengan pesan error yang merujuk ke perintah `winebox system doctor`.

