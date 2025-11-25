# main.py - rebuild-menu approach so menu titles change reliably on language change
import ctypes, sys
import tkinter as tk
from tkinter import ttk, messagebox # messagebox eklendi
import threading, time
from vc_checker import get_missing_vc
from vc_installer import install_vc
from port_checker import scan_ports
from apache_fixer import check_service, start_service
from utils.system import is_admin, is_windows
from languages import get_text, set_current_lang, languages

# --- Admin Yetkisi Kontrolü ---
# Programın kendi kendini otomatik yükseltmesini kaldırdık.
# Kullanıcıdan manuel olarak Yönetici çalıştırması bekleniyor.
if is_windows() and not ctypes.windll.shell32.IsUserAnAdmin():
    # Admin değilse uyarı göster ve çık
    messagebox.showerror(
        "Yönetici Yetkisi Gerekli", # Bu başlığı dil dosyandan çekmelisin
        "Bu programın çalışabilmesi için Yönetici olarak başlatılması gerekmektedir." # Bu metni dil dosyandan çekmelisin
    )
    sys.exit() 

# ----------------------- Tema -----------------------
LIGHT_BG = "#f0f0f0"
LIGHT_FG = "#000000"
DARK_BG = "#1e1e1e"
DARK_FG = "#ffffff"

root = tk.Tk()
root.title(get_text("title"))
root.geometry("720x570")
root.resizable(False, False)

# Title
title = tk.Label(root, text=get_text("title"), font=("Segoe UI", 18, "bold"))
title.pack(pady=10)

# Output & Scrollbar
output_frame = tk.Frame(root)
output_frame.pack(pady=5)
output = tk.Text(output_frame, height=20, width=85, insertbackground="black")
output.pack(side="left", padx=(0,5))
scrollbar = tk.Scrollbar(output_frame, command=output.yview)
scrollbar.pack(side="right", fill="y")
output.config(yscrollcommand=scrollbar.set)

# Progress bar
progress_style = ttk.Style()
progress_style.theme_use('clam')
progress_style.configure("TProgressbar", thickness=20, background="#0078d7")
progress = ttk.Progressbar(root, orient="horizontal", length=680, mode="determinate", style="TProgressbar")
progress.pack(pady=5)

# ----------------------- Dark Mode -----------------------
current_bg = LIGHT_BG
current_fg = LIGHT_FG

# Butonlar
scan_btn = tk.Button(root, text=get_text("scan"))
scan_btn.pack(pady=5)
auto_fix_btn = tk.Button(root, text=get_text("auto_fix"))
auto_fix_btn.pack(pady=5)

dark_var = tk.BooleanVar(value=False)

def apply_theme(dark_mode=False):
    global current_bg, current_fg
    if dark_mode:
        current_bg = DARK_BG
        current_fg = DARK_FG
    else:
        current_bg = LIGHT_BG
        current_fg = LIGHT_FG

    root.configure(bg=current_bg)
    title.config(bg=current_bg, fg=current_fg)
    output.config(bg="#2e2e2e" if dark_mode else "#ffffff", fg=current_fg, insertbackground=current_fg)
    progress_style.configure("TProgressbar", background="#4caf50" if dark_mode else "#0078d7")
    for btn in [scan_btn, auto_fix_btn]:
        btn.config(bg="#3a3a3a" if dark_mode else "#e0e0e0", fg=current_fg, activebackground="#555555" if dark_mode else "#d0d0d0")

apply_theme(dark_mode=False)

# ----------------------- Menu (we will rebuild this on language change) -----------------------
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# We'll keep references for later use
options_menu = None
language_menu = None

def build_menus():
    """Create menus according to current language. Call on startup and on language change."""
    global menu_bar, options_menu, language_menu

    # Clear existing menus
    menu_bar.delete(0, "end")

    # Create options menu
    options_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label=get_text("options"), menu=options_menu)
    options_menu.add_checkbutton(label=get_text("dark_mode"), variable=dark_var, command=lambda: apply_theme(dark_var.get()))
    options_menu.add_separator()
    options_menu.add_command(label=get_text("exit"), command=root.destroy)

    # Create language menu
    language_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label=get_text("language"), menu=language_menu)

    # Fill language menu
    for lang in languages.keys():
        # using default lambda capture trick
        language_menu.add_command(label=lang, command=lambda l=lang: on_language_selected(l))

def on_language_selected(lang):
    """Called when user picks a language from the menu."""
    set_current_lang(lang)
    # Update UI texts
    root.title(get_text("title")) # Pencere başlığını da güncelle
    title.config(text=get_text("title"))
    scan_btn.config(text=get_text("scan"))
    auto_fix_btn.config(text=get_text("auto_fix"))
    # Rebuild menus so labels/cascades reflect new language
    build_menus()
    # Optionally refresh logs or other text if needed
    # e.g. redraw output header if you want to show current language there:
    # output.insert(tk.END, f"Language set to: {lang}\n")

# initial build
build_menus()

# ----------------------- Logging -----------------------
def log(msg):
    output.insert(tk.END, msg + "\n")
    output.see(tk.END)

# ----------------------- Scan -----------------------
def run_scan_thread():
    threading.Thread(target=run_scan, daemon=True).start()

def run_scan():
    output.delete("1.0", tk.END)
    progress["value"] = 0

    if not is_windows():
        log(get_text("only_windows"))
        return
    if not is_admin():
        # Admin uyarısı artık burada, sadece log'da
        log(get_text("admin_warning"))
        return

    log(get_text("scan_started"))
    progress["maximum"] = 5

    # VC++
    missing = get_missing_vc()
    if missing:
        log(get_text("vc_missing_found"))
        for m in missing:
            log(f" - {m}")
    else:
        log(get_text("vc_all_installed"))
    progress["value"] = 1

    # Port kontrolü (use localized header)
    log("\n" + get_text("port_check"))
    ports = scan_ports()
    for p, info in ports.items():
        if info:
            log(get_text("port_used").format(port=p, name=info['name'], pid=info['pid']))
        else:
            log(get_text("port_status").format(port=p))
    progress["value"] = 2

    # Apache kontrol (localized header)
    log("\n" + get_text("apache_check"))
    service = check_service("wampapache64")
    if service == "RUNNING":
        log(get_text("apache_running"))
    elif service == "STOPPED":
        log(get_text("apache_stopped"))
    else:
        log(get_text("apache_status").format(status=service))
    progress["value"] = 3

    progress["value"] = 5
    log(get_text("scan_completed"))

# ----------------------- Auto-Fix -----------------------
def auto_fix_thread():
    threading.Thread(target=auto_fix, daemon=True).start()

def auto_fix():
    output.delete("1.0", tk.END)
    progress["value"] = 0

    if not is_admin():
        # Admin uyarısı artık burada, sadece log'da
        log(get_text("admin_warning"))
        return

    log(get_text("auto_fix_started"))
    progress["maximum"] = 5

    # VC++ Eksikleri
    missing = get_missing_vc()
    if missing:
        # --- KULLANICI ONAY MEKANİZMASI ---
        # Dil dosyasında bu stringlerin tanımlı olduğunu varsayıyoruz
        confirm_title = get_text("vc_install_confirm_title") 
        confirm_text = get_text("vc_install_confirm_text").format(count=len(missing))
        
        # Kullanıcıya kurulumu yapıp yapmak istemediğini sor
        if messagebox.askyesno(confirm_title, confirm_text):
            for m in missing:
                log(get_text("vc_installing").format(package=m))
                
                # vc_installer.py çağrısı sadece onaydan sonra gerçekleşiyor
                ok, msg = install_vc(m)
                log(msg)
        else:
            # Kullanıcı hayır dediyse
            log(get_text("vc_install_skipped"))
            
    else:
        log(get_text("vc_all_installed"))
    progress["value"] = 1

    # Apache Başlat
    log("\n" + get_text("apache_check"))
    service = check_service("wampapache64")
    if service != "RUNNING":
        log(get_text("apache_starting"))
        start_service("wampapache64")
        time.sleep(2)
        log(get_text("apache_started"))
    else:
        log(get_text("apache_already"))
    progress["value"] = 3

    # Port Kontrolü
    log("\n" + get_text("port_check"))
    ports = scan_ports()
    for p, info in ports.items():
        if info:
            log(get_text("port_used").format(port=p, name=info['name'], pid=info['pid']))
        else:
            log(get_text("port_status").format(port=p))
    progress["value"] = 5

    log(get_text("auto_fix_completed"))

# ----------------------- Button callbacks -----------------------
scan_btn.config(command=run_scan_thread)
auto_fix_btn.config(command=auto_fix_thread)

root.mainloop()