import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import os
import datetime
import re 

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
    ("ABT", "Cerca de / Sobre"), ("AGN", "Novamente"), ("ANT", "Antena"),
    ("AR", "Fim da mensagem"), ("AS", "Aguarde"), ("BK", "Break / Devolvo"),
    ("BN", "Entre"), ("C", "Sim / Confirmado"), ("CL", "Fechando estação"),
    ("CQ", "Chamada Geral"), ("DE", "De"), ("DX", "Estação distante"),
    ("ES", "E (conjunção)"), ("FB", "Excelente"), ("GA", "Boa tarde"),
    ("GM", "Bom dia"), ("GN", "Boa noite"), ("HI", "Risada"),
    ("HW", "Como copiou?"), ("K", "Convite"), ("KN", "Convite específico"),
    ("LID", "Operador ruim"), ("N", "Não"), ("NW", "Agora"),
    ("OM", "Amigo / Homem"), ("PSE", "Por favor"), ("PWR", "Potência"),
    ("R", "Recebido"), ("RST", "Reportagem"), ("RPT", "Repita"),
    ("RX", "Receptor"), ("SK", "Fim do contato"), ("SRI", "Desculpe"),
    ("TNX", "Obrigado"), ("TU", "Obrigado"), ("TX", "Transmissor"),
    ("UR", "Seu / Você é"), ("VY", "Muito"), ("WX", "Clima"),
    ("73", "Abraços"), ("88", "Beijos"), ("QRL", "Freq. ocupada?"),
    ("QRM", "Interferência"), ("QRN", "Estática"), ("QRO", "Aumentar pot."),
    ("QRP", "Baixa pot."), ("QRT", "Desligar"), ("QRV", "Pronto"),
    ("QRZ", "Quem chama?"), ("QSB", "Fading"), ("QSL", "Confirmado"),
    ("QSO", "Contato"), ("QSY", "Mudar freq."), ("QTH", "Localização")
]

class CWInterfaceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PP2LA CW Interface - v1.0.000.1")
        self.root.geometry("700x700")
        
        self.ser = None
        self.is_connected = False
        self.auto_cq_active = False
        self.auto_cq_timer = None
        self.settings = self.load_settings()
        
        if "macros" not in self.settings:
            self.settings["macros"] = DEFAULT_MACROS

        # --- SETUP DAS ABAS ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.tab_op = tk.Frame(self.notebook)
        self.notebook.add(self.tab_op, text="   OPERAÇÃO   ")

        self.tab_log = tk.Frame(self.notebook)
        self.notebook.add(self.tab_log, text="   LOGBOOK   ")

        self.tab_dict = tk.Frame(self.notebook)
        self.notebook.add(self.tab_dict, text="   DICIONÁRIO   ")
        
        self.tab_help = tk.Frame(self.notebook)
        self.notebook.add(self.tab_help, text="   AJUDA / MANUAL   ")

        self.setup_operation_tab()
        self.setup_logbook_tab()
        self.setup_dictionary_tab()
        self.setup_help_tab() # Nova aba de ajuda
        self.setup_hotkeys() 

    # ================== ABA OPERAÇÃO ==================
    def setup_operation_tab(self):
        # 1. CONEXÃO & VELOCIDADE
        top_frame = tk.Frame(self.tab_op)
        top_frame.pack(fill="x", padx=10, pady=5)

        # -- Conexão --
        conn_frame = tk.LabelFrame(top_frame, text="Conexão", padx=5, pady=5)
        conn_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.port_combo = ttk.Combobox(conn_frame, width=15)
        self.port_combo.pack(side="left", padx=5)
        tk.Button(conn_frame, text="⟳", command=self.refresh_ports).pack(side="left", padx=2)
        self.btn_connect = tk.Button(conn_frame, text="Conectar", command=self.toggle_connection, bg="#dddddd")
        self.btn_connect.pack(side="left", padx=5)
        self.refresh_ports()

        # -- Velocidade (WPM) --
        wpm_frame = tk.LabelFrame(top_frame, text="Velocidade (1-50 WPM)", padx=5, pady=5)
        wpm_frame.pack(side="left", fill="both", padx=5)
        self.wpm_var = tk.IntVar(value=self.settings.get("wpm", 20))
        # Spinbox para WPM
        self.spin_wpm = tk.Spinbox(wpm_frame, from_=1, to=50, textvariable=self.wpm_var, width=5, font=("Arial", 12, "bold"), command=self.send_wpm)
        self.spin_wpm.pack(side="left", padx=10, pady=2)
        self.spin_wpm.bind("<Return>", lambda e: self.send_wpm())

        # 2. DADOS DA ESTAÇÃO
        st_frame = tk.LabelFrame(self.tab_op, text="Dados da Estação", padx=5, pady=5)
        st_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(st_frame, text="Call:").grid(row=0, column=0, sticky="e")
        self.entry_call = tk.Entry(st_frame, width=8); self.entry_call.grid(row=0, column=1)
        self.entry_call.insert(0, self.settings.get("callsign", "PP2LA"))

        tk.Label(st_frame, text="Nome:").grid(row=0, column=2, sticky="e")
        self.entry_name = tk.Entry(st_frame, width=8); self.entry_name.grid(row=0, column=3)
        self.entry_name.insert(0, self.settings.get("name", "LUCAS"))

        tk.Label(st_frame, text="Grid:").grid(row=0, column=4, sticky="e")
        self.entry_grid = tk.Entry(st_frame, width=6); self.entry_grid.grid(row=0, column=5)
        self.entry_grid.insert(0, self.settings.get("grid", "GH63"))

        tk.Button(st_frame, text="Salvar", command=self.save_station_data, bg="#fff0c0").grid(row=0, column=9, padx=10)

        # 3. QSO ATUAL & LOGBOOK
        qso_frame = tk.LabelFrame(self.tab_op, text="QSO Atual & Logbook", padx=5, pady=5, bg="#f0f8ff")
        qso_frame.pack(fill="x", padx=10, pady=5)

        # Linha 1: Frequência e Banda
        row1 = tk.Frame(qso_frame, bg="#f0f8ff"); row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Banda:", bg="#f0f8ff").pack(side="left")
        self.combo_band = ttk.Combobox(row1, values=["80m","40m","30m","20m","17m","15m","12m","10m","6m","2m"], width=5)
        self.combo_band.pack(side="left", padx=5); self.combo_band.current(1)
        
        tk.Label(row1, text="Freq (kHz):", bg="#f0f8ff").pack(side="left", padx=(10,2))
        self.entry_freq = tk.Entry(row1, width=10); self.entry_freq.pack(side="left")
        self.entry_freq.insert(0, "7000")

        # Linha 2: DX Call e RST
        row2 = tk.Frame(qso_frame, bg="#f0f8ff"); row2.pack(fill="x", pady=5)
        tk.Label(row2, text="DX CALL:", font=("Arial", 11, "bold"), bg="#f0f8ff").pack(side="left")
        self.entry_dx = tk.Entry(row2, width=12, font=("Arial", 14, "bold"), bg="white", fg="blue")
        self.entry_dx.pack(side="left", padx=5)

        tk.Label(row2, text="RST(S):", bg="#f0f8ff").pack(side="left", padx=(10,2))
        self.entry_rst_sent = tk.Entry(row2, width=4, justify="center"); self.entry_rst_sent.pack(side="left"); self.entry_rst_sent.insert(0, "599")
        
        tk.Label(row2, text="RST(R):", bg="#f0f8ff").pack(side="left", padx=(10,2))
        self.entry_rst_rcvd = tk.Entry(row2, width=4, justify="center"); self.entry_rst_rcvd.pack(side="left"); self.entry_rst_rcvd.insert(0, "599")

        tk.Button(row2, text="LOGAR (Ctrl+Enter)", bg="#aaffaa", command=self.log_contact).pack(side="left", padx=20)
        tk.Button(row2, text="X", command=self.clear_qso_fields, bg="#ffcccc").pack(side="left")

        self.lbl_log_status = tk.Label(qso_frame, text="", fg="green", bg="#f0f8ff")
        self.lbl_log_status.pack(fill="x", pady=5)

        # 4. MACROS E AUTO CQ
        self.macro_frame = tk.LabelFrame(self.tab_op, text="Mensagens (F1 - F12)", padx=5, pady=5)
        self.macro_frame.pack(fill="x", padx=10, pady=5)
        
        tool = tk.Frame(self.macro_frame); tool.pack(fill="x")
        tk.Button(tool, text="⚙ EDITAR MACROS", command=self.open_editor).pack(side="left", padx=5)
        
        # Configuração Auto CQ
        cq_frame = tk.Frame(tool); cq_frame.pack(side="right")
        tk.Label(cq_frame, text="Loop (s):").pack(side="left")
        self.entry_cq_interval = tk.Entry(cq_frame, width=4)
        self.entry_cq_interval.pack(side="left", padx=2)
        self.entry_cq_interval.insert(0, self.settings.get("cq_interval", "15"))
        
        self.btn_auto_cq = tk.Button(cq_frame, text="AUTO CQ (OFF)", bg="#ffcccc", command=self.toggle_auto_cq)
        self.btn_auto_cq.pack(side="left", padx=5)

        self.buttons_container = tk.Frame(self.macro_frame); self.buttons_container.pack(fill="both", expand=True, pady=5)
        self.render_macro_buttons()

        # 5. TERMINAL
        main_frame = tk.LabelFrame(self.tab_op, text="Terminal (TEXTO LIVRE)", padx=5, pady=5)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.txt_input = tk.Entry(main_frame, font=("Courier", 12))
        self.txt_input.pack(fill="x", padx=5); self.txt_input.bind("<Return>", lambda e: self.send_text())
        
        self.log_area = scrolledtext.ScrolledText(main_frame, height=6, state='disabled', font=("Courier", 10))
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

    # ================== ABA LOGBOOK ==================
    def setup_logbook_tab(self):
        # Filtros
        filter_frame = tk.Frame(self.tab_log)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(filter_frame, text="Atualizar Lista", command=self.load_logbook).pack(side="left")
        tk.Label(filter_frame, text="   |   Filtrar por Banda:").pack(side="left")
        self.filter_band = ttk.Combobox(filter_frame, values=["TODAS", "80m","40m","20m","15m","10m"], width=8)
        self.filter_band.pack(side="left", padx=5); self.filter_band.current(0)
        self.filter_band.bind("<<ComboboxSelected>>", lambda e: self.load_logbook())

        # Tabela Treeview
        cols = ("Data", "Hora", "Call", "Banda", "Freq", "Modo", "RST(S)", "RST(R)", "Grid")
        self.log_tree = ttk.Treeview(self.tab_log, columns=cols, show="headings")
        
        for col in cols:
            self.log_tree.heading(col, text=col)
            w = 80 if col in ["Freq", "Grid"] else 60
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

            self.log_tree.insert("", 0, values=(fmt_date, fmt_time, dx, band, get_tag("FREQ", rec), 
                                                get_tag("MODE", rec), get_tag("RST_SENT", rec), 
                                                get_tag("RST_RCVD", rec), get_tag("MY_GRIDSQUARE", rec)))

    # ================== ABA AJUDA / MANUAL ==================
    def setup_help_tab(self):
        help_text = """
=== MANUAL DO USUÁRIO - PP2LA CW INTERFACE ===

1. CONEXÃO INICIAL
   - Conecte o Arduino ao PC via USB.
   - Na aba 'Operação', clique no botão '⟳' para atualizar as portas.
   - Selecione a porta COM correta e clique em 'Conectar'.
   - O status aparecerá no Terminal (ex: [SYS] Conectado: COM3).

2. CONFIGURAÇÃO DA ESTAÇÃO
   - Preencha seus dados (Call, Nome, Grid) na seção 'Dados da Estação'.
   - Clique em 'Salvar' para que eles fiquem gravados no arquivo settings.json.
   - Esses dados são usados nas Macros automáticas.

3. OPERAÇÃO EM CW
   - Terminal: Digite qualquer texto no campo inferior e aperte ENTER para transmitir em CW.
   - Velocidade: Ajuste a velocidade (WPM) na caixa numérica (1-50).
   - Parada de Emergência (ESC): Se precisar interromper uma transmissão longa, aperte a tecla ESC.

4. SISTEMA DE MACROS (F1 - F12)
   - Use as teclas F1 a F12 do teclado ou clique nos botões para enviar mensagens prontas.
   - Para editar, clique em '⚙ EDITAR MACROS'.
   - Variáveis que você pode usar nas macros:
     {call}   -> Seu Indicativo
     {name}   -> Seu Nome
     {grid}   -> Seu Grid Locator
     {target} -> Indicativo do DX (campo DX CALL)
     {rst}    -> RST Enviado (converte 599 para 5NN automaticamente)

5. AUTO CQ (CHAMADA AUTOMÁTICA)
   - O sistema envia a Macro F1 (CQ) repetidamente.
   - Defina o tempo de intervalo em segundos no campo 'Loop (s)'.
   - Clique em 'AUTO CQ' para iniciar. O botão ficará VERMELHO.
   - Se alguém responder, aperte ESC ou clique novamente para parar.

6. LOGBOOK (LIVRO DE REGISTROS)
   - Durante um QSO, preencha: DX CALL, RST Enviado/Recebido, Banda e Frequência.
   - Pressione CTRL+ENTER ou clique em 'LOGAR' para salvar.
   - O contato é salvo automaticamente no arquivo 'logbook.adi' (padrão mundial).
   - Vá na aba 'LOGBOOK' para ver todos os contatos e filtrar por banda.

7. LISTA DE ATALHOS
   [F1 - F12]      -> Enviar Macros
   [ESC]           -> Parar transmissão imediatamente (Pânico)
   [CTRL + ENTER]  -> Salvar contato no Logbook
   [PAGE UP]       -> Aumentar velocidade (+2 WPM)
   [PAGE DOWN]     -> Diminuir velocidade (-2 WPM)
"""
        
        frame = tk.Frame(self.tab_help)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        st = scrolledtext.ScrolledText(frame, font=("Courier", 11), state='normal')
        st.pack(fill="both", expand=True)
        
        # Insere o texto
        st.insert(tk.END, help_text)
        
        # Formatação simples (Negrito nos títulos)
        st.tag_config("bold", font=("Courier", 11, "bold"), foreground="blue")
        # Aplica negrito nas linhas que começam com números ou ===
        count = 1
        while True:
            idx = f"{count}.0"
            if st.compare(idx, ">=", tk.END): break
            line_text = st.get(idx, f"{idx} lineend")
            if line_text.startswith("=") or (len(line_text)>0 and line_text[0].isdigit()):
                 st.tag_add("bold", idx, f"{idx} lineend")
            count += 1

        st.configure(state='disabled') # Apenas leitura

    # ================== DICIONÁRIO ==================
    def setup_dictionary_tab(self):
        frame = tk.Frame(self.tab_dict); frame.pack(fill="x", padx=10, pady=10)
        tk.Label(frame, text="Buscar: ").pack(side="left")
        self.search_var = tk.StringVar(); self.search_var.trace("w", self.filter_dictionary)
        tk.Entry(frame, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
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
        return {"callsign": "PP2LA", "name": "LUCAS", "grid": "GH63", "wpm": 20, "macros": DEFAULT_MACROS}

    def save_station_data(self):
        try:
            cq_int = int(self.entry_cq_interval.get())
        except: cq_int = 15

        self.settings.update({
            "callsign": self.entry_call.get().upper(),
            "name": self.entry_name.get().upper(),
            "grid": self.entry_grid.get().upper(),
            "wpm": self.wpm_var.get(),
            "cq_interval": cq_int
        })
        with open(SETTINGS_FILE, "w") as f: json.dump(self.settings, f)
        self.log_system("Dados salvos!")

    def open_editor(self):
        ed = tk.Toplevel(self.root); ed.title("Editor"); ed.geometry("700x500")
        tk.Label(ed, text="{call}, {name}, {grid}, {target}, {rst}", fg="gray").pack()
        cv = tk.Canvas(ed); sb = tk.Scrollbar(ed, orient="vertical", command=cv.yview)
        fr = tk.Frame(cv); fr.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=fr, anchor="nw"); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        entries = []
        for m in self.settings["macros"]:
            row = tk.Frame(fr); row.pack(fill="x", pady=2)
            l = tk.Entry(row, width=15); l.insert(0, m["label"]); l.pack(side="left")
            t = tk.Entry(row, width=60); t.insert(0, m["template"]); t.pack(side="left")
            entries.append((l, t))
        def add_blank():
            row = tk.Frame(fr); row.pack(fill="x", pady=2); l = tk.Entry(row, width=15); l.pack(side="left"); t = tk.Entry(row, width=60); t.pack(side="left"); entries.append((l, t))
        tk.Button(ed, text="+ Linha", command=add_blank).pack(fill="x")
        def save():
            new_m = []
            for l, t in entries:
                if l.get().strip(): new_m.append({"label": l.get().strip(), "template": t.get().strip()})
            self.settings["macros"] = new_m; self.save_station_data(); self.render_macro_buttons(); ed.destroy()
        tk.Button(ed, text="SALVAR", bg="#aaffaa", command=save).pack(fill="x", padx=10, pady=10)

    def render_macro_buttons(self):
        for w in self.buttons_container.winfo_children(): w.destroy()
        r=0; c=0
        for i, m in enumerate(self.settings["macros"]):
            # Deixa claro qual é o F-key
            key_label = f"F{i+1}"
            btn_text = f"[{key_label}] {m['label']}"
            tk.Button(self.buttons_container, text=btn_text, width=15, height=2,
                      command=lambda t=m["template"]: self.send_macro(t)).grid(row=r, column=c, padx=3, pady=3)
            c+=1; 
            if c>3: c=0; r+=1

    # --- Serial ---
    def refresh_ports(self):
        self.port_combo['values'] = [p.device for p in serial.tools.list_ports.comports()]
        if self.port_combo['values']: self.port_combo.current(0)

    def toggle_connection(self):
        if not self.is_connected:
            try:
                self.ser = serial.Serial(self.port_combo.get(), 9600); self.is_connected=True
                self.btn_connect.config(text="Desconectar", bg="#ffaaaa")
                self.log_system(f"Conectado: {self.port_combo.get()}")
                threading.Thread(target=self.read_serial, daemon=True).start()
                self.root.after(500, self.send_wpm)
            except Exception as e: self.log_system(f"Erro: {e}")
        else:
            self.is_connected=False; 
            if self.ser: self.ser.close()
            self.btn_connect.config(text="Conectar", bg="#dddddd"); self.log_system("Desconectado")
            self.auto_cq_active = False; self.update_auto_cq_ui()

    def send_wpm(self):
        if self.is_connected: 
            try:
                val = int(self.wpm_var.get())
                self.ser.write(f"/wpm {val}\n".encode())
                self.log_system(f"WPM definido: {val}")
            except: pass

    def send_text(self):
        if self.txt_input.get(): self.send_raw(self.txt_input.get()); self.txt_input.delete(0, tk.END)

    def send_raw(self, t):
        if self.is_connected: 
            self.ser.write((t+"\n").encode())
            self.log_user(f"TX: {t}")
        else: self.log_system("Erro: Não conectado")

    def toggle_auto_cq(self):
        if not self.is_connected: return self.log_system("Conecte primeiro!")
        
        self.auto_cq_active = not self.auto_cq_active
        self.update_auto_cq_ui()

        if self.auto_cq_active:
            self.log_system(">>> AUTO CQ INICIADO <<<")
            self.loop_auto_cq() 
        else:
            self.log_system(">>> AUTO CQ PARADO <<<")
            if self.auto_cq_timer:
                self.root.after_cancel(self.auto_cq_timer)
                self.auto_cq_timer = None

    def update_auto_cq_ui(self):
        state = "PARAR" if self.auto_cq_active else "AUTO CQ (OFF)"
        color = "#ff5555" if self.auto_cq_active else "#ffcccc"
        self.btn_auto_cq.config(text=state, bg=color)

    def loop_auto_cq(self):
        if self.auto_cq_active and self.is_connected and self.settings["macros"]:
            self.send_macro(self.settings["macros"][0]["template"])
            try:
                interval_sec = int(self.entry_cq_interval.get())
            except:
                interval_sec = 15
            self.auto_cq_timer = self.root.after(interval_sec * 1000, self.loop_auto_cq)

    def read_serial(self):
        while self.is_connected:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: self.root.after(0, self.log_device, line)
            except: break

    def log_system(self, msg): self.append_log(f"[SYS] {msg}", "gray")
    def log_user(self, msg): self.append_log(msg, "blue")
    def log_device(self, msg): self.append_log(f"[ARD] {msg}", "green")
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
        self.root.bind('<Prior>', lambda e: self.change_speed(2)) # PageUp
        self.root.bind('<Next>', lambda e: self.change_speed(-2)) # PageDown

    def trigger_macro_by_index(self, index):
        if index < len(self.settings["macros"]):
            template = self.settings["macros"][index]["template"]
            self.send_macro(template)

    def change_speed(self, delta):
        try:
            current = int(self.wpm_var.get())
            new_val = current + delta
            if 1 <= new_val <= 50:
                self.wpm_var.set(new_val)
                self.send_wpm()
        except: pass

    def stop_transmission(self):
        self.log_system(">>> PARADA DE EMERGÊNCIA (ESC) <<<")
        if self.auto_cq_active:
            self.toggle_auto_cq()

    # ================== LOGBOOK SALVAR ==================
    def log_contact(self):
        dx_call = self.entry_dx.get().strip().upper()
        if not dx_call:
            messagebox.showwarning("Atenção", "Preencha o indicativo do DX!")
            return

        now = datetime.datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M")
        
        band = self.combo_band.get()
        freq = self.entry_freq.get().replace(",", ".") 
        mode = "CW"
        rst_s = self.entry_rst_sent.get().strip() or "599"
        rst_r = self.entry_rst_rcvd.get().strip() or "599"
        my_grid = self.entry_grid.get()

        # ADIF
        adif_record = (
            f"<CALL:{len(dx_call)}>{dx_call} "
            f"<QSO_DATE:8>{date_str} "
            f"<TIME_ON:4>{time_str} "
            f"<BAND:{len(band)}>{band} "
            f"<FREQ:{len(freq)}>{freq} "
            f"<MODE:2>{mode} "
            f"<RST_SENT:{len(rst_s)}>{rst_s} "
            f"<RST_RCVD:{len(rst_r)}>{rst_r} "
            f"<MY_GRIDSQUARE:{len(my_grid)}>{my_grid} "
            "<EOR>\n"
        )

        try:
            if not os.path.exists(LOGBOOK_FILE):
                with open(LOGBOOK_FILE, "w") as f:
                    f.write("ADIF 2.0 Export\n<PROGRAMID:5>PP2LA\n<EOH>\n\n")

            with open(LOGBOOK_FILE, "a") as f:
                f.write(adif_record)
            
            self.lbl_log_status.config(text=f"QSO {dx_call} Salvo!", fg="green")
            self.clear_qso_fields()
            self.load_logbook()
            self.root.after(3000, lambda: self.lbl_log_status.config(text=""))
            
        except Exception as e:
            messagebox.showerror("Erro ao Logar", str(e))

    def clear_qso_fields(self):
        self.entry_dx.delete(0, tk.END)
        self.entry_rst_sent.delete(0, tk.END); self.entry_rst_sent.insert(0, "599")
        self.entry_rst_rcvd.delete(0, tk.END); self.entry_rst_rcvd.insert(0, "599")
        self.entry_dx.focus()

if __name__ == "__main__":
    root = tk.Tk()
    app = CWInterfaceApp(root)
    root.mainloop()