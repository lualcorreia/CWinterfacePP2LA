import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import os
import datetime
import re
import time

SETTINGS_FILE = "settings.json"
LOGBOOK_FILE = "logbook.adi"

# --- Macros Padrão ---
DEFAULT_MACROS = [
    {"label": "F1 CQ", "template": "CQ CQ CQ DE {call} {call} {grid} K"},
    {"label": "F2 ANS", "template": "{target} DE {call} {call} KN"},
    {"label": "F3 RST", "template": "{target} DE {call} R RST {rst} {rst} BK"},
    {"label": "F4 TU", "template": "TU FB QSO 73 SK E E"},
    {"label": "F5 NAME", "template": "NAME {name} {name} BK"},
    {"label": "F6 QTH", "template": "QTH {grid} {grid} BK"},
    {"label": "F7 QRZ?", "template": "QRZ? DE {call}"},
    {"label": "F8 QRL?", "template": "QRL? DE {call}"},
    {"label": "F9 AGN?", "template": "AGN? AGN?"},
    {"label": "F10 HW?", "template": "HW? BK"},
    {"label": "F11 CALL", "template": "{call} {call}"},
    {"label": "F12 73", "template": "73 TU"},
]

CW_DICTIONARY = [
    ("ABT", "Cerca de"), ("AGN", "Novamente"), ("ANT", "Antena"),
    ("AR", "Fim da mensagem"), ("AS", "Aguarde"), ("BK", "Break / Devolvo"),
    ("CQ", "Chamada Geral"), ("DE", "De"), ("DX", "Estação distante"),
    ("FB", "Excelente"), ("K", "Convite"), ("KN", "Convite específico"),
    ("NW", "Agora"), ("OM", "Amigo"), ("PSE", "Por favor"), 
    ("PWR", "Potência"), ("R", "Recebido"), ("RST", "Reportagem"), 
    ("RX", "Receptor"), ("SK", "Fim do contato"), ("SRI", "Desculpe"),
    ("TNX", "Obrigado"), ("TU", "Obrigado"), ("TX", "Transmissor"),
    ("73", "Abraços"), ("QRL", "Freq. ocupada?"), ("QRM", "Interferência"), 
    ("QRN", "Estática"), ("QRO", "Aumentar pot."), ("QRP", "Baixa pot."), 
    ("QRT", "Desligar"), ("QRV", "Pronto"), ("QRZ", "Quem chama?"), 
    ("QSB", "Fading"), ("QSL", "Confirmado"), ("QSO", "Contato"), 
    ("QSY", "Mudar freq."), ("QTH", "Localização")
]

class CWInterfaceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PP2LA CW Interface")
        self.root.geometry("750x780")
        
        # Estilo Moderno
        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
            
        self.style.configure("TButton", font=("Segoe UI", 9))
        self.style.configure("TLabelFrame", font=("Segoe UI", 10, "bold"))
        self.style.configure("Log.TButton", font=("Segoe UI", 10, "bold"), background="#aaffaa")
        self.style.configure("Stop.TButton", font=("Segoe UI", 10, "bold"), background="#ff7777", foreground="white")
        
        self.ser = None
        self.is_connected = False
        self.auto_cq_active = False
        self.auto_cq_timer = None
        self.settings = self.load_settings()
        
        if "macros" not in self.settings:
            self.settings["macros"] = DEFAULT_MACROS

        # --- SETUP DAS ABAS ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_op = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_op, text="   OPERAÇÃO   ")

        self.tab_log = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text="   LOGBOOK   ")

        self.tab_dict = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dict, text="   DICIONÁRIO   ")
        
        self.setup_operation_tab()
        self.setup_logbook_tab()
        self.setup_dictionary_tab()
        self.setup_hotkeys() 

    # ================== ABA OPERAÇÃO ==================
    def setup_operation_tab(self):
        # 1. CONEXÃO & VELOCIDADE
        top_frame = ttk.Frame(self.tab_op)
        top_frame.pack(fill="x", padx=10, pady=5)

        conn_frame = ttk.LabelFrame(top_frame, text="Sistema", padding=5)
        conn_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.port_combo = ttk.Combobox(conn_frame, width=12)
        self.port_combo.pack(side="left", padx=5)
        ttk.Button(conn_frame, text="⟳", width=3, command=self.refresh_ports).pack(side="left", padx=2)
        self.btn_connect = ttk.Button(conn_frame, text="Conectar", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=5)
        self.refresh_ports()
        
        # LED TX
        self.lbl_tx_led = tk.Label(conn_frame, text="● OFF", fg="gray", font=("Segoe UI", 12, "bold"))
        self.lbl_tx_led.pack(side="right", padx=15)

        wpm_frame = ttk.LabelFrame(top_frame, text="Velocidade (WPM)", padding=5)
        wpm_frame.pack(side="left", fill="both")
        self.wpm_var = tk.IntVar(value=self.settings.get("wpm", 20))
        self.spin_wpm = ttk.Spinbox(wpm_frame, from_=1, to=50, textvariable=self.wpm_var, width=5, command=self.send_wpm)
        self.spin_wpm.pack(side="left", padx=10)
        self.spin_wpm.bind("<Return>", lambda e: self.send_wpm())

        # 2. DADOS DA ESTAÇÃO
        st_frame = ttk.LabelFrame(self.tab_op, text="Meus Dados", padding=5)
        st_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(st_frame, text="Call:").grid(row=0, column=0, sticky="e", padx=5)
        self.entry_call = ttk.Entry(st_frame, width=10); self.entry_call.grid(row=0, column=1)
        self.entry_call.insert(0, self.settings.get("callsign", "PP2LA"))

        ttk.Label(st_frame, text="Nome:").grid(row=0, column=2, sticky="e", padx=5)
        self.entry_name = ttk.Entry(st_frame, width=10); self.entry_name.grid(row=0, column=3)
        self.entry_name.insert(0, self.settings.get("name", "LUCAS"))

        ttk.Label(st_frame, text="Grid:").grid(row=0, column=4, sticky="e", padx=5)
        self.entry_grid = ttk.Entry(st_frame, width=8); self.entry_grid.grid(row=0, column=5)
        self.entry_grid.insert(0, self.settings.get("grid", "GH63"))
        
        ttk.Label(st_frame, text="Ref SOTA/POTA:").grid(row=0, column=6, sticky="e", padx=5)
        self.entry_my_pota = ttk.Entry(st_frame, width=12); self.entry_my_pota.grid(row=0, column=7)
        self.entry_my_pota.insert(0, self.settings.get("my_pota", ""))

        ttk.Button(st_frame, text="Salvar Perfil", command=self.save_station_data).grid(row=0, column=8, padx=15)

        # 3. QSO ATUAL & LOGBOOK
        qso_frame = ttk.LabelFrame(self.tab_op, text="Log de Contato", padding=10)
        qso_frame.pack(fill="x", padx=10, pady=5)

        row1 = ttk.Frame(qso_frame); row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Banda:").pack(side="left")
        self.combo_band = ttk.Combobox(row1, values=["80m","40m","30m","20m","17m","15m","12m","10m","6m","2m"], width=5)
        self.combo_band.pack(side="left", padx=5); self.combo_band.current(1)
        
        ttk.Label(row1, text="Freq (kHz):").pack(side="left", padx=(10,2))
        self.entry_freq = ttk.Entry(row1, width=8); self.entry_freq.pack(side="left")
        self.entry_freq.insert(0, "7000")
        
        ttk.Label(row1, text="DX SOTA/POTA:").pack(side="left", padx=(15,2))
        self.entry_dx_pota = ttk.Entry(row1, width=12); self.entry_dx_pota.pack(side="left")

        row2 = ttk.Frame(qso_frame); row2.pack(fill="x", pady=8)
        ttk.Label(row2, text="DX CALL:", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.entry_dx = tk.Entry(row2, width=12, font=("Consolas", 14, "bold"), fg="#0044cc", bg="#f8f9fa", relief="solid", borderwidth=1)
        self.entry_dx.pack(side="left", padx=10)

        ttk.Label(row2, text="RST(S):").pack(side="left")
        self.entry_rst_sent = ttk.Entry(row2, width=4, justify="center"); self.entry_rst_sent.pack(side="left", padx=2)
        self.entry_rst_sent.insert(0, "599")
        
        ttk.Label(row2, text="RST(R):").pack(side="left", padx=(10,2))
        self.entry_rst_rcvd = ttk.Entry(row2, width=4, justify="center"); self.entry_rst_rcvd.pack(side="left", padx=2)
        self.entry_rst_rcvd.insert(0, "599")

        ttk.Button(row2, text="LOGAR QSO", style="Log.TButton", command=self.log_contact).pack(side="left", padx=20)
        ttk.Button(row2, text="Limpar", command=self.clear_qso_fields).pack(side="left")

        self.lbl_log_status = ttk.Label(qso_frame, text="", foreground="green")
        self.lbl_log_status.pack(fill="x")

        # 4. MACROS E AUTO CQ
        self.macro_frame = ttk.LabelFrame(self.tab_op, text="Macros (F1 - F12)", padding=5)
        self.macro_frame.pack(fill="x", padx=10, pady=5)
        
        tool = ttk.Frame(self.macro_frame); tool.pack(fill="x", pady=5)
        ttk.Button(tool, text="⚙ Editar", command=self.open_editor).pack(side="left")
        
        cq_frame = ttk.Frame(tool); cq_frame.pack(side="right")
        ttk.Label(cq_frame, text="Loop (s):").pack(side="left")
        self.entry_cq_interval = ttk.Entry(cq_frame, width=4)
        self.entry_cq_interval.pack(side="left", padx=5)
        self.entry_cq_interval.insert(0, self.settings.get("cq_interval", "15"))
        
        self.btn_auto_cq = ttk.Button(cq_frame, text="▶ AUTO CQ", command=self.toggle_auto_cq)
        self.btn_auto_cq.pack(side="left")

        self.buttons_container = ttk.Frame(self.macro_frame)
        self.buttons_container.pack(fill="both", expand=True, pady=5)
        self.render_macro_buttons()

        # 5. TERMINAL
        main_frame = ttk.LabelFrame(self.tab_op, text="Terminal de Transmissão", padding=5)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.txt_input = ttk.Entry(main_frame, font=("Consolas", 12))
        self.txt_input.pack(fill="x", padx=5, pady=5)
        self.txt_input.bind("<Return>", lambda e: self.send_text())
        
        self.log_area = scrolledtext.ScrolledText(main_frame, height=7, state='disabled', font=("Consolas", 10), bg="#1e1e1e", fg="#cccccc")
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    # ================== ABA LOGBOOK ==================
    def setup_logbook_tab(self):
        filter_frame = ttk.Frame(self.tab_log)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(filter_frame, text="Atualizar Lista", command=self.load_logbook).pack(side="left")
        ttk.Label(filter_frame, text="  Filtrar Banda:").pack(side="left", padx=5)
        self.filter_band = ttk.Combobox(filter_frame, values=["TODAS", "80m","40m","20m","15m","10m"], width=8)
        self.filter_band.pack(side="left"); self.filter_band.current(0)
        self.filter_band.bind("<<ComboboxSelected>>", lambda e: self.load_logbook())

        cols = ("Data", "Hora", "Call", "Banda", "Freq", "Modo", "RST(S)", "RST(R)", "SOTA/POTA")
        self.log_tree = ttk.Treeview(self.tab_log, columns=cols, show="headings")
        
        for col in cols:
            self.log_tree.heading(col, text=col)
            w = 80 if col in ["Freq", "SOTA/POTA"] else 60
            if col == "Data": w = 90
            if col == "Call": w = 100
            self.log_tree.column(col, width=w, anchor="center")

        sb = ttk.Scrollbar(self.tab_log, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscroll=sb.set)
        sb.pack(side="right", fill="y")
        self.log_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.load_logbook()

    def load_logbook(self):
        for i in self.log_tree.get_children(): self.log_tree.delete(i)
        if not os.path.exists(LOGBOOK_FILE): return
        target_band = self.filter_band.get()
        
        with open(LOGBOOK_FILE, "r", encoding="utf-8", errors="ignore") as f: content = f.read()
        records = content.split("<EOR>")
        for rec in records:
            if not rec.strip(): continue
            def get_tag(tag, text):
                m = re.search(f"<{tag}:\d+>([^<]+)", text, re.IGNORECASE)
                return m.group(1).strip() if m else ""

            dx = get_tag("CALL", rec)
            if not dx: continue
            band = get_tag("BAND", rec)
            if target_band != "TODAS" and band.upper() != target_band.upper(): continue

            date = get_tag("QSO_DATE", rec)
            time = get_tag("TIME_ON", rec)
            fmt_date = f"{date[6:8]}/{date[4:6]}/{date[0:4]}" if len(date)==8 else date
            fmt_time = f"{time[0:2]}:{time[2:4]}" if len(time)==4 else time
            
            pota = get_tag("SIG_INFO", rec)

            self.log_tree.insert("", 0, values=(fmt_date, fmt_time, dx, band, get_tag("FREQ", rec), 
                                                get_tag("MODE", rec), get_tag("RST_SENT", rec), 
                                                get_tag("RST_RCVD", rec), pota))

    # ================== DICIONÁRIO ==================
    def setup_dictionary_tab(self):
        frame = ttk.Frame(self.tab_dict); frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(frame, text="Buscar: ").pack(side="left")
        self.search_var = tk.StringVar(); self.search_var.trace("w", self.filter_dictionary)
        ttk.Entry(frame, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
        
        cols = ("abrev", "meaning")
        self.tree = ttk.Treeview(self.tab_dict, columns=cols, show="headings")
        self.tree.heading("abrev", text="Abreviação"); self.tree.column("abrev", width=100, anchor="center")
        self.tree.heading("meaning", text="Significado"); self.tree.column("meaning", width=500, anchor="w")
        
        sb = ttk.Scrollbar(self.tab_dict, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.populate_tree(CW_DICTIONARY)

    def populate_tree(self, data):
        for i in self.tree.get_children(): self.tree.delete(i)
        for item in data: self.tree.insert("", tk.END, values=item)

    def filter_dictionary(self, *args):
        q = self.search_var.get().lower()
        data = [(a, m) for a, m in CW_DICTIONARY if q in a.lower() or q in m.lower()]
        self.populate_tree(data)

    # ================== LÓGICA GERAL ==================
    def flash_tx_led(self):
        self.lbl_tx_led.config(text="● ON AIR", fg="red")
        self.root.after(800, lambda: self.lbl_tx_led.config(text="● OFF", fg="gray"))

    def get_formatted_rst(self):
        val = self.entry_rst_sent.get().strip().upper()
        return "5NN" if val == "599" else val

    def send_macro(self, template):
        call = self.entry_call.get().upper()
        name = self.entry_name.get().upper()
        grid = self.entry_grid.get().upper()
        target = self.entry_dx.get().upper().strip() or "DX"
        rst = self.get_formatted_rst()
        msg = template.format(call=call, name=name, grid=grid, target=target, rst=rst)
        self.send_raw(msg)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f: return json.load(f)
            except: pass
        return {"callsign": "PP2LA", "name": "LUCAS", "grid": "GH63", "my_pota": "", "wpm": 20, "macros": DEFAULT_MACROS}

    def save_station_data(self):
        try:
            cq_int = int(self.entry_cq_interval.get())
        except: cq_int = 15

        self.settings.update({
            "callsign": self.entry_call.get().upper(),
            "name": self.entry_name.get().upper(),
            "grid": self.entry_grid.get().upper(),
            "my_pota": self.entry_my_pota.get().upper(),
            "wpm": self.wpm_var.get(),
            "cq_interval": cq_int
        })
        with open(SETTINGS_FILE, "w") as f: json.dump(self.settings, f)
        self.log_system("Perfil salvo!")

    def open_editor(self):
        ed = tk.Toplevel(self.root); ed.title("Editor de Macros"); ed.geometry("700x500")
        ttk.Label(ed, text="Variáveis: {call}, {name}, {grid}, {target}, {rst}").pack(pady=5)
        
        cv = tk.Canvas(ed); sb = ttk.Scrollbar(ed, orient="vertical", command=cv.yview)
        fr = ttk.Frame(cv); fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=fr, anchor="nw"); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        
        entries = []
        for m in self.settings["macros"]:
            row = ttk.Frame(fr); row.pack(fill="x", pady=2, padx=10)
            l = ttk.Entry(row, width=15); l.insert(0, m["label"]); l.pack(side="left", padx=5)
            t = ttk.Entry(row, width=60); t.insert(0, m["template"]); t.pack(side="left")
            entries.append((l, t))
            
        def save():
            new_m = []
            for l, t in entries:
                if l.get().strip(): new_m.append({"label": l.get().strip(), "template": t.get().strip()})
            self.settings["macros"] = new_m; self.save_station_data(); self.render_macro_buttons(); ed.destroy()
            
        ttk.Button(ed, text="SALVAR MACROS", style="Log.TButton", command=save).pack(fill="x", padx=10, pady=10)

    def render_macro_buttons(self):
        for w in self.buttons_container.winfo_children(): w.destroy()
        r=0; c=0
        for i, m in enumerate(self.settings["macros"]):
            btn_text = f"F{i+1} | {m['label']}"
            ttk.Button(self.buttons_container, text=btn_text, width=18,
                      command=lambda t=m["template"]: self.send_macro(t)).grid(row=r, column=c, padx=4, pady=4)
            c+=1; 
            if c>3: c=0; r+=1

    # --- Serial ---
    def refresh_ports(self):
        self.port_combo['values'] = [p.device for p in serial.tools.list_ports.comports()]
        if self.port_combo['values']: self.port_combo.current(0)

    def toggle_connection(self):
        if not self.is_connected:
            try:
                self.ser = serial.Serial(self.port_combo.get(), 9600, timeout=0.1) 
                self.is_connected = True
                self.btn_connect.config(text="Desconectar")
                self.log_system(f"Conectado: {self.port_combo.get()}")
                threading.Thread(target=self.read_serial, daemon=True).start()
                self.root.after(500, self.send_wpm)
            except Exception as e: 
                self.log_system(f"Erro: {e}")
        else:
            self.is_connected = False 
            if self.ser: self.ser.close()
            self.btn_connect.config(text="Conectar")
            self.log_system("Desconectado")
            self.auto_cq_active = False; self.update_auto_cq_ui()

    def send_wpm(self):
        if self.is_connected: 
            try:
                val = int(self.wpm_var.get())
                self.ser.write(f"/wpm {val}\n".encode())
                self.log_system(f"WPM: {val}")
            except: pass

    def send_text(self):
        if self.txt_input.get(): 
            self.send_raw(self.txt_input.get())
            self.txt_input.delete(0, tk.END)

    def send_raw(self, t):
        if self.is_connected: 
            self.ser.write((t + "\n").encode())
            self.log_user(f"TX: {t}")
            self.flash_tx_led()
        else: 
            self.log_system("Erro: Interface offline.")

    def toggle_auto_cq(self):
        if not self.is_connected: return self.log_system("Conecte primeiro!")
        self.auto_cq_active = not self.auto_cq_active
        self.update_auto_cq_ui()
        if self.auto_cq_active:
            self.log_system(">>> AUTO CQ ATIVADO <<<")
            self.loop_auto_cq() 
        else:
            self.log_system(">>> AUTO CQ PARADO <<<")
            if self.auto_cq_timer:
                self.root.after_cancel(self.auto_cq_timer)
                self.auto_cq_timer = None

    def update_auto_cq_ui(self):
        if self.auto_cq_active:
            self.btn_auto_cq.config(text="⏹ PARAR CQ", style="Stop.TButton")
        else:
            self.btn_auto_cq.config(text="▶ AUTO CQ", style="TButton")

    def loop_auto_cq(self):
        if self.auto_cq_active and self.is_connected and self.settings["macros"]:
            self.send_macro(self.settings["macros"][0]["template"])
            try: interval_sec = int(self.entry_cq_interval.get())
            except: interval_sec = 15
            self.auto_cq_timer = self.root.after(interval_sec * 1000, self.loop_auto_cq)

    def read_serial(self):
        while self.is_connected:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: self.root.after(0, self.log_device, line)
                else:
                    time.sleep(0.05) 
            except Exception: break

    def log_system(self, msg): self.append_log(f"[SYS] {msg}", "#00ff00")
    def log_user(self, msg): self.append_log(msg, "#00ccff")
    def log_device(self, msg): self.append_log(f"[ARD] {msg}", "#ffcc00")
    
    def append_log(self, text, color):
        self.log_area.config(state='normal')
        self.log_area.tag_config(color, foreground=color)
        self.log_area.insert(tk.END, text + "\n", color)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    # ================== HOTKEYS ==================
    def setup_hotkeys(self):
        for i in range(12):
            self.root.bind(f'<F{i+1}>', lambda event, idx=i: self.trigger_macro_by_index(idx))
        self.root.bind('<Escape>', lambda e: self.stop_transmission())
        self.root.bind('<Control-Return>', lambda e: self.log_contact())
        self.root.bind('<Prior>', lambda e: self.change_speed(2)) 
        self.root.bind('<Next>', lambda e: self.change_speed(-2)) 

    def trigger_macro_by_index(self, index):
        if index < len(self.settings["macros"]):
            self.send_macro(self.settings["macros"][index]["template"])

    def change_speed(self, delta):
        try:
            new_val = int(self.wpm_var.get()) + delta
            if 1 <= new_val <= 50:
                self.wpm_var.set(new_val)
                self.send_wpm()
        except: pass

    def stop_transmission(self):
        self.log_system(">>> PARADA (ESC) <<<")
        if self.auto_cq_active: self.toggle_auto_cq()

    # ================== LOGBOOK SALVAR ==================
    def log_contact(self):
        dx_call = self.entry_dx.get().strip().upper()
        if not dx_call: return messagebox.showwarning("Atenção", "Preencha o DX CALL!")

        now = datetime.datetime.utcnow()
        date_str, time_str = now.strftime("%Y%m%d"), now.strftime("%H%M")
        
        band = self.combo_band.get()
        freq = self.entry_freq.get().replace(",", ".") 
        rst_s = self.entry_rst_sent.get().strip() or "599"
        rst_r = self.entry_rst_rcvd.get().strip() or "599"
        my_grid = self.entry_grid.get()
        
        my_sig = self.entry_my_pota.get().strip().upper()
        dx_sig = self.entry_dx_pota.get().strip().upper()

        adif_record = (
            f"<CALL:{len(dx_call)}>{dx_call} "
            f"<QSO_DATE:8>{date_str} <TIME_ON:4>{time_str} "
            f"<BAND:{len(band)}>{band} <FREQ:{len(freq)}>{freq} "
            f"<MODE:2>CW <RST_SENT:{len(rst_s)}>{rst_s} "
            f"<RST_RCVD:{len(rst_r)}>{rst_r} "
            f"<MY_GRIDSQUARE:{len(my_grid)}>{my_grid} "
        )
        if my_sig: adif_record += f"<MY_SIG_INFO:{len(my_sig)}>{my_sig} "
        if dx_sig: adif_record += f"<SIG_INFO:{len(dx_sig)}>{dx_sig} "
        adif_record += "<EOR>\n"

        try:
            if not os.path.exists(LOGBOOK_FILE):
                with open(LOGBOOK_FILE, "w") as f: f.write("ADIF 2.0 Export\n<PROGRAMID:5>PP2LA\n<EOH>\n\n")
            with open(LOGBOOK_FILE, "a") as f: f.write(adif_record)
            
            self.lbl_log_status.config(text=f"QSO {dx_call} Logado com sucesso!")
            self.clear_qso_fields()
            self.load_logbook()
            self.root.after(3000, lambda: self.lbl_log_status.config(text=""))
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def clear_qso_fields(self):
        self.entry_dx.delete(0, tk.END)
        self.entry_rst_sent.delete(0, tk.END); self.entry_rst_sent.insert(0, "599")
        self.entry_rst_rcvd.delete(0, tk.END); self.entry_rst_rcvd.insert(0, "599")
        self.entry_dx_pota.delete(0, tk.END)
        self.entry_dx.focus()

if __name__ == "__main__":
    root = tk.Tk()
    app = CWInterfaceApp(root)
    root.mainloop()
