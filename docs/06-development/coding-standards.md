# Coding Standards

Standar penulisan kode untuk WineBox:

1. **Python Version:** Python >= 3.11.
2. **Type Annotations:** Wajib menggunakan type hints penuh (`typing`, `dataclasses`, `pathlib.Path`).
3. **Pemisahan Layer:**
   - Layer domain tidak boleh mengimpor infrastructure atau CLI.
   - CLI tidak boleh memanggil biner OS secara langsung tanpa melalui service layer.
4. **Formatter & Linter:** Menggunakan **Ruff** dengan panjang baris maksimal 100 karakter.
5. **Path Handling:** Wajib menggunakan `pathlib.Path` untuk semua operasi jalur berkas (hindari manipulasi string mentah).
6. **Error Handling:** Gunakan hierarchy class dari `winebox.common.exceptions`. Jangan membiarkan unhandled raw system exceptions lolos ke pengguna terminal.

