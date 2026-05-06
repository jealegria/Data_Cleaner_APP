import os
import csv
import re
import json
import threading
import chardet
import sys
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog, messagebox
from pathlib import Path

# Fix para UI borrosa en pantallas con alto DPI (Windows)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def get_asset_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / "assets"

from core.scanner import *
from core.normalizer import *
from core.presets import hpn_guardia_process

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Type Tool — Advanced Data Scanning")
        self.geometry("1100x900")
        self.minsize(850, 700)
        self.configure(bg="#0B0B0E")
        
        # Paths for PyInstaller compatibility
        self.base_path = get_base_path()
        self.asset_path = get_asset_path()
        
        # Modern Icon
        try:
            icon_path = self.asset_path / "app_icon.png"
            if icon_path.exists():
                self.icon_img = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(False, self.icon_img)
        except Exception:
            pass
        
        self.config_path = self.base_path / "config.json"
        
        # Premium Dark Palette
        self.BG          = "#0B0B0E"
        self.PANEL       = "#161B22"
        self.BORDER      = "#30363D"
        self.ACCENT      = "#58A6FF"
        self.BTN_BG      = "#21262D"
        self.BTN_HOVER   = "#30363D"
        self.BTN_EXECUTE = "#238636"
        self.TEXT        = "#C9D1D9"
        self.SUBTEXT     = "#8B949E"
        self.DANGER      = "#F85149"
        self.SUCCESS     = "#3FB950"
        self.CONSOLE     = "#0D1117"

        self.FONT_UI      = ("Segoe UI", 10)
        self.FONT_BOLD    = ("Segoe UI Semibold", 10)
        self.FONT_TITLE   = ("Segoe UI", 16, "bold")
        self.FONT_CONSOLE = ("Consolas", 10)
        self.FONT_BTN     = ("Segoe UI Semibold", 10)
        
        self.entrada_var = tk.StringVar()
        self.salida_var  = tk.StringVar()
        self.modify_file_var = tk.StringVar()
        self.modify_salida_var = tk.StringVar()
        self.preset_file_var = tk.StringVar()
        self.preset_action_var = tk.StringVar(value="Select Preset Action...")
        
        # Specific Vars for Guardia HPN Process 1
        self.hpn_adultos_var = tk.StringVar()
        self.hpn_pediatria_var = tk.StringVar()
        self.hpn_output_var = tk.StringVar()
        
        self.consolidar_var = tk.BooleanVar()
        
        self.df_modify = None
        self.mod_checkboxes = {} # {col_name: BooleanVar}
        self.current_mod_subtab = 0
        self.presets = {} # {name: [cols]}

        self.preset_details = {
            "Select Preset Action...": "Selecciona una acción para ver su descripción.",
            "Guardia HPN Process 1": (
                "Esta acción consolida y limpia datos de Guardia HPN (Adultos y Pediatría).\n\n"
                "PROCESO:\n"
                "• Consolidación: Une archivos de ambas carpetas con trazabilidad por 'servicio'.\n"
                "• Deduplicación: Elimina registros duplicados basados en 'id'.\n"
                "• Limpieza DNI: Crea la col 'dni' extrayendo solo números de 'documento'.\n"
                "• Cálculo Edad: Crea 'edad_dias' (entero) procesando años, meses y días.\n"
                "• Limpieza CIE10: Extrae solo el código (ej: K08.8) de la descripción.\n"
                "• Formato Final: Mantiene solo las 14 columnas requeridas para Supabase."
            ),
            "Other placeholder action...": "Descripción de la otra acción de prueba."
        }
        
        self._load_config()
        
        # Watch for changes to save automatically
        self.entrada_var.trace_add("write", lambda *args: self._save_config())
        self.salida_var.trace_add("write", lambda *args: self._save_config())
        self.modify_salida_var.trace_add("write", lambda *args: self._save_config())
        self.hpn_adultos_var.trace_add("write", lambda *args: self._save_config())
        self.hpn_pediatria_var.trace_add("write", lambda *args: self._save_config())
        self.hpn_output_var.trace_add("write", lambda *args: self._save_config())
        
        self._build_ui()

    def _load_config(self):
        defaults = {
            "input": str(Path.home() / "Desktop" / "csv_crudos"),
            "output": str(Path.home() / "Desktop" / "csv_limpios"),
            "modify_output": str(Path.home() / "Desktop" / "csv_limpios"),
            "presets": {},
            "hpn_adultos": "",
            "hpn_pediatria": "",
            "hpn_output": ""
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    cfg = json.load(f)
                    self.entrada_var.set(cfg.get("input", defaults["input"]))
                    self.salida_var.set(cfg.get("output", defaults["output"]))
                    self.modify_salida_var.set(cfg.get("modify_output", defaults["modify_output"]))
                    self.hpn_adultos_var.set(cfg.get("hpn_adultos", defaults["hpn_adultos"]))
                    self.hpn_pediatria_var.set(cfg.get("hpn_pediatria", defaults["hpn_pediatria"]))
                    self.hpn_output_var.set(cfg.get("hpn_output", defaults["hpn_output"]))
                    self.presets = cfg.get("presets", {})
                    return
            except:
                pass
        self.entrada_var.set(defaults["input"])
        self.salida_var.set(defaults["output"])
        self.modify_salida_var.set(defaults["modify_output"])
        self.hpn_adultos_var.set(defaults["hpn_adultos"])
        self.hpn_pediatria_var.set(defaults["hpn_pediatria"])
        self.hpn_output_var.set(defaults["hpn_output"])
        self.presets = defaults["presets"]


    def _save_config(self):
        cfg = {
            "input": self.entrada_var.get(),
            "output": self.salida_var.get(),
            "modify_output": self.modify_salida_var.get(),
            "hpn_adultos": self.hpn_adultos_var.get(),
            "hpn_pediatria": self.hpn_pediatria_var.get(),
            "hpn_output": self.hpn_output_var.get(),
            "presets": self.presets
        }
        try:
            with open(self.config_path, "w") as f:
                json.dump(cfg, f)
        except:
            pass

    def _build_ui(self):
        def make_btn(parent, text, cmd, color=self.BTN_BG, fg=self.TEXT, width=None, row=0, col=0):
            b = tk.Button(parent, text=text, command=cmd,
                          font=self.FONT_BTN, bg=color, fg=fg,
                          activebackground=self.BTN_HOVER, activeforeground="white",
                          relief="flat", bd=0, padx=15, pady=8, cursor="hand2",
                          width=width)
            b.grid(row=row, column=col, padx=4)
            return b

        # ── Header Section ────────────────────────────────────
        hdr = tk.Frame(self, bg=self.PANEL, padx=25)
        hdr.pack(fill="x", pady=(18, 18))
        
        logo_frame = tk.Frame(hdr, bg=self.PANEL)
        logo_frame.pack(side="left")
        
        tk.Label(logo_frame, text="⚡ TYPE TOOL",
                 font=self.FONT_TITLE, bg=self.PANEL, fg=self.ACCENT).pack(side="left")
        tk.Label(logo_frame, text=" |  Data Intelligence",
                 font=("Segoe UI", 11), bg=self.PANEL, fg=self.SUBTEXT).pack(side="left", padx=(5, 0), pady=(4, 0))
        
        tk.Label(hdr, text="v1.3.1",
                 font=("Segoe UI", 9), bg=self.PANEL, fg=self.SUBTEXT).pack(side="right", pady=(8, 0))
        
        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x")

        # ── Main Tab Navigation ──────────────────────────────
        main_tab_bar = tk.Frame(self, bg=self.BG, padx=25, pady=10)
        main_tab_bar.pack(fill="x")

        def switch_main_tab(idx):
            self.current_main_tab = idx
            for i, b in enumerate(self.main_tab_btns):
                b.config(fg=self.TEXT if i == idx else self.SUBTEXT,
                         bg=self.PANEL if i == idx else self.BG)
            
            if idx == 0:
                self.frame_modify.pack_forget()
                self.frame_presets.pack_forget()
                self.frame_process.pack(fill="both", expand=True)
            elif idx == 1:
                self.frame_process.pack_forget()
                self.frame_presets.pack_forget()
                self.frame_modify.pack(fill="both", expand=True)
            else:
                self.frame_process.pack_forget()
                self.frame_modify.pack_forget()
                self.frame_presets.pack(fill="both", expand=True)

        self.main_tab_btns = []
        t1 = tk.Button(main_tab_bar, text="PROCESS DATA", font=self.FONT_BOLD, 
                       bg=self.PANEL, fg=self.TEXT, relief="flat", padx=20, pady=10, 
                       cursor="hand2", command=lambda: switch_main_tab(0))
        t1.pack(side="left", padx=(0, 5))
        self.main_tab_btns.append(t1)

        t2 = tk.Button(main_tab_bar, text="MODIFY DATA", font=self.FONT_BOLD, 
                       bg=self.BG, fg=self.SUBTEXT, relief="flat", padx=20, pady=10, 
                       cursor="hand2", command=lambda: switch_main_tab(1))
        t2.pack(side="left", padx=(0, 5))
        self.main_tab_btns.append(t2)

        t3 = tk.Button(main_tab_bar, text="QUICK PRESETS", font=self.FONT_BOLD, 
                       bg=self.BG, fg=self.SUBTEXT, relief="flat", padx=20, pady=10, 
                       cursor="hand2", command=lambda: switch_main_tab(2))
        t3.pack(side="left")
        self.main_tab_btns.append(t3)

        # ── Content Area ──────────────────────────────────────
        self.content_area = tk.Frame(self, bg=self.BG)
        self.content_area.pack(fill="both", expand=True)

        # ── TAB 1: Process Data ──────────────────────────────
        self.frame_process = tk.Frame(self.content_area, bg=self.BG)
        self.frame_process.pack(fill="both", expand=True)

        # Configuration Section (Compact)
        cfg_section = tk.Frame(self.frame_process, bg=self.BG, padx=25)
        cfg_section.pack(fill="x", pady=10)
        cfg_section.columnconfigure(0, weight=1)

        # Row 1: Source
        tk.Label(cfg_section, text="SOURCE PATH", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        
        in_row = tk.Frame(cfg_section, bg=self.BG)
        in_row.grid(row=1, column=0, sticky="ew")
        in_row.columnconfigure(0, weight=1)

        ef_in = tk.Frame(in_row, bg=self.BORDER, padx=1, pady=1)
        ef_in.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Entry(ef_in, textvariable=self.entrada_var, font=self.FONT_UI, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", bd=8).pack(fill="x")
        
        make_btn(in_row, "📄 File", self._sel_archivo, row=0, col=1)
        make_btn(in_row, "📂 Folder", self._sel_carpeta, row=0, col=2)
        make_btn(in_row, "🚀 Open", lambda: self._open_dir(self.entrada_var.get()), color=self.ACCENT, fg="white", row=0, col=3)

        # Row 2: Output
        tk.Label(cfg_section, text="OUTPUT DESTINATION", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(
            row=2, column=0, sticky="w", pady=(15, 5))
        
        out_row = tk.Frame(cfg_section, bg=self.BG)
        out_row.grid(row=3, column=0, sticky="ew")
        out_row.columnconfigure(0, weight=1)

        ef_out = tk.Frame(out_row, bg=self.BORDER, padx=1, pady=1)
        ef_out.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Entry(ef_out, textvariable=self.salida_var, font=self.FONT_UI, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", bd=8).pack(fill="x")
        
        make_btn(out_row, "📂 Folder", self._sel_salida, row=0, col=1)
        make_btn(out_row, "🚀 Open", lambda: self._open_dir(self.salida_var.get()), color=self.ACCENT, fg="white", row=0, col=2)

        # Row 3: Options
        opts_frame = tk.Frame(cfg_section, bg=self.BG)
        opts_frame.grid(row=4, column=0, sticky="w", pady=(15, 0))

        tk.Checkbutton(opts_frame, text="Consolidate multiple files into one", 
                       variable=self.consolidar_var, font=self.FONT_UI,
                       bg=self.BG, fg=self.TEXT, selectcolor=self.PANEL,
                       activebackground=self.BG, activeforeground=self.TEXT,
                       cursor="hand2").pack(side="left")

        # Action Buttons
        action_bar = tk.Frame(self.frame_process, bg=self.BG, padx=25, pady=15)
        action_bar.pack(fill="x")

        self.btn_analizar = tk.Button(
            action_bar, text="🔍 ANALYZE DATA",
            command=lambda: self._ejecutar("analizar"),
            font=("Segoe UI", 11, "bold"),
            bg="#238636", fg="white",
            activebackground="#2EA043", activeforeground="white",
            relief="flat", bd=0, padx=35, pady=12, cursor="hand2"
        )
        self.btn_analizar.pack(side="left", padx=(0, 15))

        self.btn_norm = tk.Button(
            action_bar, text="🚀 NORMALIZE & SAVE",
            command=lambda: self._ejecutar("normalizar"),
            font=("Segoe UI", 11, "bold"),
            bg=self.ACCENT, fg="white",
            activebackground="#388BFD", activeforeground="white",
            relief="flat", bd=0, padx=35, pady=12, cursor="hand2"
        )
        self.btn_norm.pack(side="left")

        self.status = tk.Label(action_bar, text="", font=self.FONT_UI, bg=self.BG, fg=self.SUBTEXT)
        self.status.pack(side="right")

        tk.Frame(self.frame_process, bg=self.BORDER, height=1).pack(fill="x", pady=(5, 0))

        # Output Area (Consoles)
        tab_area = tk.Frame(self.frame_process, bg=self.PANEL)
        tab_area.pack(fill="both", expand=True)

        tab_bar_cons = tk.Frame(tab_area, bg=self.PANEL, padx=25)
        tab_bar_cons.pack(fill="x", pady=(15, 0))

        def make_tab_btn(parent, text, idx):
            b = tk.Button(parent, text=text, font=("Segoe UI Semibold", 10),
                          bg=self.PANEL, fg=self.ACCENT if idx==0 else self.SUBTEXT,
                          activebackground=self.PANEL, activeforeground=self.TEXT,
                          relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
                          command=lambda: self._switch_tab(idx))
            b.pack(side="left")
            return b

        self.btn_tab_log = make_tab_btn(tab_bar_cons, "PROCESS LOG", 0)
        self.btn_tab_schema = make_tab_btn(tab_bar_cons, "DB SCHEMA INSIGHTS", 1)

        # Tools on the right
        tools_frame = tk.Frame(tab_bar_cons, bg=self.PANEL)
        tools_frame.pack(side="right")
        tools_frame.columnconfigure(0, weight=1)
        tools_frame.columnconfigure(1, weight=1)
        make_btn(tools_frame, "📋 Copy", self._copiar, width=10, row=0, col=0)
        make_btn(tools_frame, "🧹 Clear", self._limpiar, fg=self.DANGER, width=10, row=0, col=1)

        self.console_container = tk.Frame(tab_area, bg=self.PANEL, padx=25)
        self.console_container.pack(fill="both", expand=True, pady=(5, 20))

        self.console_log = scrolledtext.ScrolledText(
            self.console_container, font=self.FONT_CONSOLE, bg=self.CONSOLE, fg="#7EE787",
            insertbackground=self.TEXT, relief="flat", bd=10, wrap="none", state="disabled"
        )
        self.console_schema = scrolledtext.ScrolledText(
            self.console_container, font=self.FONT_CONSOLE, bg=self.CONSOLE, fg="#79C0FF",
            insertbackground=self.TEXT, relief="flat", bd=10, wrap="none", state="disabled"
        )
        self.hs = tk.Scrollbar(self.console_container, orient="horizontal")
        self.hs.pack(side="bottom", fill="x")

        self.console_log.pack(fill="both", expand=True)
        self.console_log.config(xscrollcommand=self.hs.set)
        self.console_schema.config(xscrollcommand=self.hs.set)
        self.hs.config(command=self._on_scroll)

        # ── TAB 2: Modify Data ───────────────────────────────
        self.frame_modify = tk.Frame(self.content_area, bg=self.BG)
        
        # Modify Header
        mod_cfg = tk.Frame(self.frame_modify, bg=self.BG, padx=25, pady=10)
        mod_cfg.pack(fill="x")
        mod_cfg.columnconfigure(0, weight=1)

        tk.Label(mod_cfg, text="EXPLORE & PREPARE FOR SUPABASE", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(
            row=0, column=0, sticky="w", pady=(0, 5))

        mod_in_row = tk.Frame(mod_cfg, bg=self.BG)
        mod_in_row.grid(row=1, column=0, sticky="ew")
        mod_in_row.columnconfigure(0, weight=1)

        ef_mod = tk.Frame(mod_in_row, bg=self.BORDER, padx=1, pady=1)
        ef_mod.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Entry(ef_mod, textvariable=self.modify_file_var, font=self.FONT_UI, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", bd=8).pack(fill="x")
        
        make_btn(mod_in_row, "📄 File", self._sel_archivo_modify, row=0, col=1)
        make_btn(mod_in_row, "🚀 Open", lambda: self._open_dir(self.modify_file_var.get()), color=self.ACCENT, fg="white", row=0, col=2)

        # Output selection for Modify
        tk.Label(mod_cfg, text="OUTPUT DESTINATION", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(
            row=2, column=0, sticky="w", pady=(15, 5))
        
        mod_out_row = tk.Frame(mod_cfg, bg=self.BG)
        mod_out_row.grid(row=3, column=0, sticky="ew")
        mod_out_row.columnconfigure(0, weight=1)

        ef_mod_out = tk.Frame(mod_out_row, bg=self.BORDER, padx=1, pady=1)
        ef_mod_out.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Entry(ef_mod_out, textvariable=self.modify_salida_var, font=self.FONT_UI, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, relief="flat", bd=8).pack(fill="x")
        
        make_btn(mod_out_row, "📂 Folder", self._sel_salida_modify, row=0, col=1)
        make_btn(mod_out_row, "🚀 Open", lambda: self._open_dir(self.modify_salida_var.get()), color=self.ACCENT, fg="white", row=0, col=2)
        
        # Action
        mod_action = tk.Frame(self.frame_modify, bg=self.BG, padx=25, pady=10)
        mod_action.pack(fill="x")
        
        self.btn_extract = tk.Button(
            mod_action, text="🔍 EXTRACT INFO",
            command=self._ejecutar_modify,
            font=("Segoe UI", 11, "bold"),
            bg="#238636", fg="white",
            activebackground="#2EA043", activeforeground="white",
            relief="flat", bd=0, padx=35, pady=12, cursor="hand2"
        )
        self.btn_extract.pack(side="left", padx=(0, 15))

        self.btn_save_filtered = tk.Button(
            mod_action, text="💾 SAVE FILTERED CSV",
            command=self._save_filtered_csv,
            font=("Segoe UI", 11, "bold"),
            bg=self.ACCENT, fg="white",
            activebackground="#388BFD", activeforeground="white",
            relief="flat", bd=0, padx=35, pady=12, cursor="hand2",
            state="disabled"
        )
        self.btn_save_filtered.pack(side="left")

        tk.Frame(self.frame_modify, bg=self.BORDER, height=1).pack(fill="x", pady=(15, 0))

        # Sub-Tab Navigation for Modify
        mod_sub_bar = tk.Frame(self.frame_modify, bg=self.BG, padx=25)
        mod_sub_bar.pack(fill="x", pady=(10, 0))
        
        def switch_mod_subtab(idx):
            self.current_mod_subtab = idx
            for i, b in enumerate(self.mod_sub_btns):
                is_active = (i == idx)
                b.config(fg=self.ACCENT if is_active else self.SUBTEXT,
                         font=self.FONT_BOLD if is_active else self.FONT_UI)
            
            if idx == 0:
                self.mod_tab_area_console.pack_forget()
                self.frame_mod_selector.pack(fill="both", expand=True)
            else:
                self.frame_mod_selector.pack_forget()
                self.mod_tab_area_console.pack(fill="both", expand=True)

        self.mod_sub_btns = []
        ms1 = tk.Button(mod_sub_bar, text="SELECT COLUMNS", font=self.FONT_BOLD, 
                        bg=self.BG, fg=self.ACCENT, relief="flat", padx=15, pady=8, 
                        cursor="hand2", command=lambda: switch_mod_subtab(0))
        ms1.pack(side="left")
        self.mod_sub_btns.append(ms1)

        ms2 = tk.Button(mod_sub_bar, text="STRUCTURE REPORT", font=self.FONT_BOLD, 
                        bg=self.BG, fg=self.SUBTEXT, relief="flat", padx=15, pady=8, 
                        cursor="hand2", command=lambda: switch_mod_subtab(1))
        ms2.pack(side="left")
        self.mod_sub_btns.append(ms2)

        # Content for Modify Tabs
        self.frame_mod_selector = tk.Frame(self.frame_modify, bg=self.BG)
        self.frame_mod_selector.pack(fill="both", expand=True)

        # Column Selector Area
        sel_label_frame = tk.Frame(self.frame_mod_selector, bg=self.BG, padx=25)
        sel_label_frame.pack(fill="x", pady=(15, 0))
        tk.Label(sel_label_frame, text="TICK THE COLUMNS YOU WANT TO EXPORT", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).pack(side="left")

        # Select All / Deselect All / Presets UI
        tools_row = tk.Frame(self.frame_mod_selector, bg=self.BG, padx=25)
        tools_row.pack(fill="x", pady=(5, 0))
        
        make_btn(tools_row, "✅ Select All", lambda: self._toggle_all_cols(True), row=0, col=0)
        make_btn(tools_row, "❌ Deselect All", lambda: self._toggle_all_cols(False), row=0, col=1)
        
        tk.Label(tools_row, text="  |  PRESETS:", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(row=0, column=2)
        
        self.preset_var = tk.StringVar(value="Select Preset...")
        self.preset_menu = tk.OptionMenu(tools_row, self.preset_var, "Select Preset...", *self._get_preset_list(), command=self._apply_preset)
        self.preset_menu.config(font=self.FONT_UI, bg=self.BTN_BG, fg=self.TEXT, relief="flat", highlightthickness=0, bd=0)
        self.preset_menu["menu"].config(font=self.FONT_UI, bg=self.BTN_BG, fg=self.TEXT)
        self.preset_menu.grid(row=0, column=3, padx=10)
        
        make_btn(tools_row, "💾 Save Selection as Preset", self._save_selection_as_preset, color=self.BTN_BG, row=0, col=4)
        make_btn(tools_row, "🗑️ Delete", self._delete_preset, color=self.DANGER, row=0, col=5)

        self.sel_container = tk.Frame(self.frame_mod_selector, bg=self.BG, padx=25, pady=10)
        self.sel_container.pack(fill="both", expand=True)
        
        self.sel_canvas = tk.Canvas(self.sel_container, bg=self.PANEL, highlightthickness=1, highlightbackground=self.BORDER)
        self.sel_scrollbar = tk.Scrollbar(self.sel_container, orient="vertical", command=self.sel_canvas.yview)
        self.sel_scrollable_frame = tk.Frame(self.sel_canvas, bg=self.PANEL)

        self.sel_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.sel_canvas.configure(scrollregion=self.sel_canvas.bbox("all"))
        )

        self.sel_canvas.create_window((0, 0), window=self.sel_scrollable_frame, anchor="nw")
        self.sel_canvas.configure(yscrollcommand=self.sel_scrollbar.set)

        self.sel_canvas.pack(side="left", fill="both", expand=True)
        self.sel_scrollbar.pack(side="right", fill="y")

        # Console Area (now a fixed sub-tab)
        self.mod_tab_area_console = tk.Frame(self.frame_modify, bg=self.PANEL)
        
        mod_tool_bar = tk.Frame(self.mod_tab_area_console, bg=self.PANEL, padx=25, pady=10)
        mod_tool_bar.pack(fill="x")
        tk.Label(mod_tool_bar, text="DATA STRUCTURE INSIGHTS", font=self.FONT_BOLD, bg=self.PANEL, fg=self.ACCENT).pack(side="left")

        mod_tools = tk.Frame(mod_tool_bar, bg=self.PANEL)
        mod_tools.pack(side="right")
        make_btn(mod_tools, "📋 Copy", self._copiar_modify, width=10, row=0, col=0)
        make_btn(mod_tools, "🧹 Clear", self._limpiar_modify, fg=self.DANGER, width=10, row=0, col=1)

        self.console_modify = scrolledtext.ScrolledText(
            self.mod_tab_area_console, font=self.FONT_CONSOLE, bg=self.CONSOLE, fg="#79C0FF",
            insertbackground=self.TEXT, relief="flat", bd=10, wrap="none", state="disabled"
        )
        self.mod_hs = tk.Scrollbar(self.mod_tab_area_console, orient="horizontal", command=self.console_modify.xview)
        self.console_modify.config(xscrollcommand=self.mod_hs.set)
        
        self.console_modify.pack(fill="both", expand=True, padx=25)
        self.mod_hs.pack(fill="x", padx=25, pady=(0, 20))

        switch_mod_subtab(0)

        # ── TAB 3: Quick Presets ──────────────────────────────
        self.frame_presets = tk.Frame(self.content_area, bg=self.BG)
        # self.frame_presets will be packed via switch_main_tab
        
        # Presets Header
        pre_cfg = tk.Frame(self.frame_presets, bg=self.BG, padx=25, pady=10)
        pre_cfg.pack(fill="x")
        pre_cfg.columnconfigure(0, weight=1)

        tk.Label(pre_cfg, text="ONE-CLICK AUTOMATION PRESETS", font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).grid(
            row=0, column=0, sticky="w", pady=(0, 5))

        # Action Selection
        action_row = tk.Frame(pre_cfg, bg=self.BG)
        action_row.grid(row=1, column=0, sticky="ew", pady=(5, 15))
        
        tk.Label(action_row, text="SELECT ACTION:", font=self.FONT_BOLD, bg=self.BG, fg=self.TEXT).pack(side="left", padx=(0, 10))
        
        self.preset_action_menu = tk.OptionMenu(action_row, self.preset_action_var, 
                                              "Guardia HPN Process 1", 
                                              "Other placeholder action...",
                                              command=self._update_preset_inputs)
        self.preset_action_menu.config(font=self.FONT_UI, bg=self.BTN_BG, fg=self.TEXT, relief="flat", highlightthickness=0, bd=0)
        self.preset_action_menu["menu"].config(font=self.FONT_UI, bg=self.BTN_BG, fg=self.TEXT)
        self.preset_action_menu.pack(side="left")

        # Info Button
        self.btn_preset_info = tk.Button(action_row, text="ⓘ", font=("Segoe UI", 12),
                                        bg=self.BG, fg=self.ACCENT, activebackground=self.BG,
                                        activeforeground="white", relief="flat", bd=0, 
                                        cursor="hand2", command=self._show_preset_info)
        self.btn_preset_info.pack(side="left", padx=5)

        # Dynamic Inputs Container
        self.preset_inputs_frame = tk.Frame(self.frame_presets, bg=self.BG, padx=25)
        self.preset_inputs_frame.pack(fill="x")
        
        self._update_preset_inputs() # Initialize UI

        # Execute Button
        pre_action_bar = tk.Frame(self.frame_presets, bg=self.BG, padx=25, pady=15)
        pre_action_bar.pack(fill="x")
        
        self.btn_run_preset = tk.Button(
            pre_action_bar, text="⚡ EXECUTE PRESET",
            command=self._ejecutar_preset,
            font=("Segoe UI", 11, "bold"),
            bg="#238636", fg="white",
            activebackground="#2EA043", activeforeground="white",
            relief="flat", bd=0, padx=35, pady=12, cursor="hand2"
        )
        self.btn_run_preset.pack(side="left")

        tk.Frame(self.frame_presets, bg=self.BORDER, height=1).pack(fill="x", pady=(5, 0))

        # Preset Console Area
        pre_tab_area = tk.Frame(self.frame_presets, bg=self.PANEL)
        pre_tab_area.pack(fill="both", expand=True)

        pre_tool_bar = tk.Frame(pre_tab_area, bg=self.PANEL, padx=25, pady=10)
        pre_tool_bar.pack(fill="x")
        tk.Label(pre_tool_bar, text="PRESET EXECUTION CONSOLE", font=self.FONT_BOLD, bg=self.PANEL, fg=self.ACCENT).pack(side="left")

        pre_tools = tk.Frame(pre_tool_bar, bg=self.PANEL)
        pre_tools.pack(side="right")
        make_btn(pre_tools, "📋 Copy", self._copiar_preset, width=10, row=0, col=0)
        make_btn(pre_tools, "🧹 Clear", self._limpiar_preset, fg=self.DANGER, width=10, row=0, col=1)

        self.console_presets = scrolledtext.ScrolledText(
            pre_tab_area, font=self.FONT_CONSOLE, bg=self.CONSOLE, fg="#D2A8FF",
            insertbackground=self.TEXT, relief="flat", bd=10, wrap="none", state="disabled"
        )
        self.pre_hs = tk.Scrollbar(pre_tab_area, orient="horizontal", command=self.console_presets.xview)
        self.console_presets.config(xscrollcommand=self.pre_hs.set)
        
        self.console_presets.pack(fill="both", expand=True, padx=25)
        self.pre_hs.pack(fill="x", padx=25, pady=(0, 20))

        self._switch_mod_subtab = switch_mod_subtab
        # Start on the first sub-tab
        switch_mod_subtab(0)

        # Initialize
        self.current_tab = 0
        self.current_main_tab = 0
        self._log("  Type Tool ready. Select source to begin.\n")

    # ── Callbacks y UI helpers ────────────────────────────────

    def _open_dir(self, path):
        p = Path(path)
        if not p.exists():
            self._log(f"[ERROR] Path does not exist: {path}")
            return
        os.startfile(p if p.is_dir() else p.parent)

    def _on_scroll(self, *args):
        if self.current_tab == 0:
            self.console_log.xview(*args)
        else:
            self.console_schema.xview(*args)

    def _switch_tab(self, idx):
        self.current_tab = idx
        if idx == 0:
            self.btn_tab_log.config(fg=self.ACCENT)
            self.btn_tab_schema.config(fg=self.SUBTEXT)
            self.console_schema.pack_forget()
            self.console_log.pack(fill="both", expand=True)
        else:
            self.btn_tab_schema.config(fg=self.ACCENT)
            self.btn_tab_log.config(fg=self.SUBTEXT)
            self.console_log.pack_forget()
            self.console_schema.pack(fill="both", expand=True)

    def _sel_archivo(self):
        r = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Data Files", "*.csv *.xls *.xlsx *.txt *.tsv"), ("All Files", "*.*")]
        )
        if r:
            self.entrada_var.set(r)

    def _sel_carpeta(self):
        r = filedialog.askdirectory(title="Select Input Folder")
        if r:
            self.entrada_var.set(r)

    def _sel_salida(self):
        r = filedialog.askdirectory(title="Select Output Folder")
        if r:
            self.salida_var.set(r)

    def _escribir_consola(self, widget, texto):
        def _w():
            widget.configure(state="normal")
            widget.insert("end", texto + "\n")
            widget.see("end")
            widget.configure(state="disabled")
        self.after(0, _w)

    def _log(self, texto):
        self._escribir_consola(self.console_log, texto)

    def _log_schema(self, texto):
        self._escribir_consola(self.console_schema, texto)

    def _limpiar(self):
        for w in [self.console_log, self.console_schema]:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        self.status.config(text="")

    def _copiar(self):
        widget = self.console_log if self.current_tab == 0 else self.console_schema
        contenido = widget.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(contenido)
        self.status.config(text="[OK] Copiado al portapapeles", fg="#3fb950")
        self.after(3000, lambda: self.status.config(text=""))

    # ── Modify Tab Methods ────────────────────────────────────

    def _sel_archivo_modify(self):
        r = filedialog.askopenfilename(
            title="Select Normalized CSV",
            filetypes=[("CSV Files", "*.csv")]
        )
        if r:
            self.modify_file_var.set(r)

    def _limpiar_modify(self):
        self.console_modify.configure(state="normal")
        self.console_modify.delete("1.0", "end")
        self.console_modify.configure(state="disabled")

    def _copiar_modify(self):
        contenido = self.console_modify.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(contenido)
        self.status.config(text="[OK] Estructura copiada", fg="#3fb950")
        self.after(3000, lambda: self.status.config(text=""))

    def _ejecutar_modify(self):
        ruta = self.modify_file_var.get().strip()
        if not ruta: return
        
        self.btn_extract.config(state="disabled")
        self._limpiar_modify()
        
        # Switch to Structure Report sub-tab automatically
        self._switch_mod_subtab(1)
        
        # Clear checkboxes
        for widget in self.sel_scrollable_frame.winfo_children():
            widget.destroy()
        self.mod_checkboxes = {}

        def run():
            try:
                df, enc, sep = cargar_csv(ruta)
                df = limpiar_datos(df)
                self.df_modify = df
                
                output = []
                output.append(f"FILE: {Path(ruta).name}")
                output.append(f"ENCODING: {enc}")
                output.append(f"SEPARATOR: {sep}")
                output.append(f"ROWS: {len(df):,}")
                output.append(f"COLS: {len(df.columns)}")
                output.append("-" * 40)
                output.append("STRUCTURE INSIGHTS (Ready for AI/Supabase):")
                output.append("-" * 40)

                for i, col in enumerate(df.columns):
                    serie = df[col]
                    tipo = inferir_tipo_supabase(serie)
                    nulos = serie.isna().sum()
                    ejemplo = serie.dropna().iloc[0] if not serie.dropna().empty else "NULL"
                    
                    linea = f"• {col:<25} | {tipo:<10} | Nulls: {nulos:<5} | Ex: {ejemplo}"
                    output.append(linea)

                    # Create checkbox in GUI
                    var = tk.BooleanVar(value=True)
                    self.mod_checkboxes[col] = var
                    self.after(0, lambda c=col, v=var, r=i//4, cl=i%4: 
                        tk.Checkbutton(self.sel_scrollable_frame, text=c, variable=v,
                                     bg=self.PANEL, fg=self.TEXT, selectcolor=self.BG,
                                     activebackground=self.PANEL, activeforeground=self.ACCENT,
                                     font=self.FONT_UI).grid(row=r, column=cl, sticky="w", padx=10, pady=2)
                    )
                
                final_text = "\n".join(output)
                self._escribir_consola(self.console_modify, final_text)
                self.after(0, lambda: self.btn_save_filtered.config(state="normal"))
                self.after(0, lambda: self._switch_mod_subtab(0))
                
            except Exception as e:
                self._escribir_consola(self.console_modify, f"[ERROR] {e}")
            finally:
                self.after(0, lambda: self.btn_extract.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _sel_salida_modify(self):
        r = filedialog.askdirectory(title="Select Output Folder")
        if r:
            self.modify_salida_var.set(r)

    def _toggle_all_cols(self, state):
        for var in self.mod_checkboxes.values():
            var.set(state)

    def _get_preset_list(self):
        return sorted(list(self.presets.keys())) if self.presets else ["No presets yet"]

    def _update_preset_menu(self):
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        for p in self._get_preset_list():
            menu.add_command(label=p, command=lambda v=p: self._apply_preset(v))
        self.preset_var.set("Select Preset...")

    def _apply_preset(self, val):
        if val not in self.presets: return
        self.preset_var.set(val)
        selected_cols = self.presets[val]
        for col, var in self.mod_checkboxes.items():
            var.set(col in selected_cols)

    def _save_selection_as_preset(self):
        # Custom styled dialog for modern look
        dialog = tk.Toplevel(self)
        dialog.title("Save Preset")
        dialog.geometry("400x180")
        dialog.configure(bg=self.PANEL)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center dialog
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 90
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="PRESET NAME", font=self.FONT_BOLD, bg=self.PANEL, fg=self.ACCENT).pack(pady=(20, 10))
        
        name_var = tk.StringVar()
        ef = tk.Frame(dialog, bg=self.BORDER, padx=1, pady=1)
        ef.pack(padx=30, fill="x")
        entry = tk.Entry(ef, textvariable=name_var, font=self.FONT_UI, bg=self.BG, fg=self.TEXT, 
                         insertbackground=self.TEXT, relief="flat", bd=5)
        entry.pack(fill="x")
        entry.focus_set()

        def confirm(event=None):
            name = name_var.get().strip()
            if not name: return
            
            selected_cols = [col for col, var in self.mod_checkboxes.items() if var.get()]
            if not selected_cols:
                self.status.config(text="[WARN] Selection is empty", fg=self.DANGER)
                dialog.destroy()
                return
                
            self.presets[name] = selected_cols
            self._save_config()
            self._update_preset_menu()
            self.status.config(text=f"[OK] Preset '{name}' saved", fg=self.SUCCESS)
            dialog.destroy()

        entry.bind("<Return>", confirm)
        
        btn_frame = tk.Frame(dialog, bg=self.PANEL)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, font=self.FONT_BOLD, 
                  bg=self.BTN_BG, fg=self.TEXT, relief="flat", padx=20, pady=5, cursor="hand2").pack(side="left", padx=10)
        tk.Button(btn_frame, text="SAVE", command=confirm, font=self.FONT_BOLD, 
                  bg=self.ACCENT, fg="white", relief="flat", padx=20, pady=5, cursor="hand2").pack(side="left", padx=10)
        

    def _delete_preset(self):
        val = self.preset_var.get()
        if val in self.presets:
            if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete preset '{val}'?"):
                return
            del self.presets[val]
            self._save_config()
            self._update_preset_menu()
            self.status.config(text=f"[OK] Preset deleted", fg=self.SUCCESS)

    def _show_preset_info(self):
        accion = self.preset_action_var.get()
        descr = self.preset_details.get(accion, "Sin descripción disponible.")

        # Custom Dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Info: {accion}")
        dialog.geometry("500x400")
        dialog.configure(bg=self.PANEL)
        dialog.transient(self)
        dialog.grab_set()

        # Center
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 250
        y = self.winfo_y() + (self.winfo_height() // 2) - 175
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text=accion.upper(), font=self.FONT_TITLE, bg=self.PANEL, fg=self.ACCENT).pack(pady=(20, 10))
        
        txt_frame = tk.Frame(dialog, bg=self.BORDER, padx=1, pady=1)
        txt_frame.pack(padx=30, fill="both", expand=True)
        
        txt = tk.Text(txt_frame, font=self.FONT_UI, bg=self.BG, fg=self.TEXT, 
                      padx=15, pady=15, relief="flat", wrap="word")
        txt.insert("1.0", descr)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True)

        tk.Button(dialog, text="CERRAR", command=dialog.destroy, font=self.FONT_BOLD, 
                  bg=self.BTN_BG, fg=self.TEXT, relief="flat", padx=30, pady=8, cursor="hand2").pack(pady=20)

    def _save_filtered_csv(self):
        if self.df_modify is None: return
        
        cols_to_keep = [col for col, var in self.mod_checkboxes.items() if var.get()]
        if not cols_to_keep:
            self.status.config(text="[WARN] Selecciona al menos una columna", fg=self.DANGER)
            return
            
        ruta_orig = Path(self.modify_file_var.get())
        salida_dir = Path(self.modify_salida_var.get())
        os.makedirs(salida_dir, exist_ok=True)
        
        ruta_salida = salida_dir / f"{ruta_orig.stem}_filtered.csv"
        
        try:
            df_filtered = self.df_modify[cols_to_keep]
            df_filtered.to_csv(ruta_salida, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
            
            self._limpiar_modify()
            self._switch_mod_subtab(1)
            self._escribir_consola(self.console_modify, f"DONE! Filtered CSV saved successfully.\n\n"
                                                      f"NEW FILE: {ruta_salida.name}\n"
                                                      f"ENCODING: {EXPORT_ENCODING}\n"
                                                      f"SEPARATOR: {EXPORT_SEP}\n"
                                                      f"PATH: {ruta_salida}\n"
                                                      f"COLUMNS KEPT: {len(cols_to_keep)}")
            
            self.status.config(text="[OK] CSV filtrado guardado", fg="#3fb950")
            os.startfile(salida_dir)
        except Exception as e:
            self.status.config(text=f"[ERROR] {e}", fg=self.DANGER)

    # ── Presets Tab Methods ───────────────────────────────────
    
    def _update_preset_inputs(self, *args):
        # Clear existing inputs
        for widget in self.preset_inputs_frame.winfo_children():
            widget.destroy()
            
        accion = self.preset_action_var.get()
        
        def make_field(parent, label, var, is_folder=True):
            f = tk.Frame(parent, bg=self.BG, pady=5)
            f.pack(fill="x")
            
            tk.Label(f, text=label, font=self.FONT_BOLD, bg=self.BG, fg=self.SUBTEXT).pack(side="top", anchor="w")
            
            row = tk.Frame(f, bg=self.BG)
            row.pack(fill="x", pady=(2, 0))
            row.columnconfigure(0, weight=1)
            
            ef = tk.Frame(row, bg=self.BORDER, padx=1, pady=1)
            ef.grid(row=0, column=0, sticky="ew", padx=(0, 10))
            tk.Entry(ef, textvariable=var, font=self.FONT_UI, bg=self.PANEL, fg=self.TEXT,
                     insertbackground=self.TEXT, relief="flat", bd=8).pack(fill="x")
            
            def sel():
                if is_folder:
                    r = filedialog.askdirectory(title=f"Select {label}")
                else:
                    r = filedialog.asksaveasfilename(
                        title=f"Select {label}",
                        defaultextension=".csv",
                        filetypes=[("CSV Files", "*.csv")]
                    )
                if r: var.set(r)
                
            tk.Button(row, text="📂 Folder" if is_folder else "💾 Save As", 
                      command=sel, font=self.FONT_BTN, bg=self.BTN_BG, fg=self.TEXT,
                      activebackground=self.BTN_HOVER, relief="flat", bd=0, padx=15, pady=8, cursor="hand2").grid(row=0, column=1, padx=4)
            
            tk.Button(row, text="🚀 Open", 
                      command=lambda: self._open_dir(var.get()), font=self.FONT_BTN, bg=self.ACCENT, fg="white",
                      activebackground=self.BTN_HOVER, relief="flat", bd=0, padx=15, pady=8, cursor="hand2").grid(row=0, column=2, padx=4)

        if accion == "Guardia HPN Process 1":
            make_field(self.preset_inputs_frame, "GUARDIA ADULTOS FOLDER", self.hpn_adultos_var, is_folder=True)
            make_field(self.preset_inputs_frame, "GUARDIA PEDIATRÍA FOLDER", self.hpn_pediatria_var, is_folder=True)
            make_field(self.preset_inputs_frame, "OUTPUT FILE (CSV)", self.hpn_output_var, is_folder=False)
        else:
            # Default fallback or "Select Preset Action..."
            tk.Label(self.preset_inputs_frame, text="Select a preset to see required inputs.", 
                     font=self.FONT_UI, bg=self.BG, fg=self.SUBTEXT).pack(pady=20)

    def _sel_archivo_preset(self):
        # No longer used in dynamic UI
        pass

    def _limpiar_preset(self):
        self.console_presets.configure(state="normal")
        self.console_presets.delete("1.0", "end")
        self.console_presets.configure(state="disabled")

    def _copiar_preset(self):
        contenido = self.console_presets.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(contenido)
        self.status.config(text="[OK] Consola copiada", fg="#3fb950")
        self.after(3000, lambda: self.status.config(text=""))

    def _log_preset(self, texto):
        self._escribir_consola(self.console_presets, texto)

    def _ejecutar_preset(self):
        accion = self.preset_action_var.get()
        
        if accion == "Select Preset Action...":
            self._log_preset("[WARN] Selecciona una acción de la lista.")
            return

        # Simple validation
        if accion == "Guardia HPN Process 1":
            if not self.hpn_adultos_var.get() or not self.hpn_pediatria_var.get() or not self.hpn_output_var.get():
                self._log_preset("[WARN] Por favor completa todas las rutas.")
                return
        
        self.btn_run_preset.config(state="disabled")
        self._log_preset(f"🚀 INICIANDO: {accion}")
        self._log_preset("-" * 30)

        def run():
            try:
                if accion == "Guardia HPN Process 1":
                    self._run_guardia_hpn_logic()
                else:
                    self._log_preset(f"[INFO] Ejecutando {accion}...")
                    import time
                    time.sleep(1)
                    self._log_preset("✅ Finalizado.")
            except Exception as e:
                self._log_preset(f"❌ [ERROR] {e}")
            finally:
                self.after(0, lambda: self.btn_run_preset.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _run_guardia_hpn_logic(self):
        adultos_path = self.hpn_adultos_var.get()
        pediatria_path = self.hpn_pediatria_var.get()
        output_path = self.hpn_output_var.get()
        
        # Call the modular logic
        hpn_guardia_process.run(
            adultos_path, 
            pediatria_path, 
            output_path, 
            self._log_preset
        )
        
        self.status.config(text="[OK] Guardia HPN terminada", fg="#3fb950")
        os.startfile(Path(output_path).parent)


    def _ejecutar(self, accion):
        entrada = self.entrada_var.get().strip()
        salida  = self.salida_var.get().strip()
        
        if not entrada:
            self._log("[WARN] Ingresa una ruta de entrada.")
            return
            
        if accion == "normalizar" and not salida:
            self._log("[WARN] Ingresa una carpeta de salida para guardar los archivos.")
            return

        self.btn_analizar.config(state="disabled")
        self.btn_norm.config(state="disabled")
        self.status.config(text="Procesando...", fg="#7d8590")
        
        # Volvemos al Tab de LOG para ver el progreso real en vivo
        self._switch_tab(0)

        def run():
            try:
                p = Path(entrada)
                if p.is_file():
                    archivos = [entrada]
                elif p.is_dir():
                    archivos = [
                        str(f) for f in p.iterdir()
                        if f.suffix.lower() in ['.csv', '.xls', '.xlsx', '.txt', '.tsv']
                    ]
                    if not archivos:
                        self._log("[WARN] No se encontraron archivos compatibles en la carpeta.")
                        return
                    self._log(f"[INFO] {len(archivos)} archivo(s) encontrado(s).")
                else:
                    self._log("[ERROR] Ruta de entrada no valida.")
                    return

                if accion == "normalizar":
                    os.makedirs(salida, exist_ok=True)

                df_consolidados = []
                consolidar = self.consolidar_var.get()

                # Limpiar consola de esquemas vieja antes de generar las nuevas
                self.after(0, lambda: self.console_schema.configure(state="normal"))
                self.after(0, lambda: self.console_schema.delete("1.0", "end"))
                self.after(0, lambda: self.console_schema.configure(state="disabled"))

                for archivo in archivos:
                    # 1. Procesar archivo (limpieza general y fechas)
                    df_res = procesar_archivo(archivo, salida, self._log, accion)
                    
                    if df_res is not None:
                        # 2. Generar el reporte del esquema usando el df LIMPIO
                        generar_reporte_esquema(df_res, Path(archivo).name, self._log_schema)
                        
                        # 3. Guardar en lista si vamos a consolidar
                        if accion == "normalizar" and consolidar:
                            df_consolidados.append(df_res)

                if accion == "normalizar" and consolidar and df_consolidados:
                    self._log(f"\n{'═' * 65}")
                    self._log("  CONSOLIDANDO ARCHIVOS...")
                    self._log(f"{'═' * 65}")
                    try:
                        df_final = pd.concat(df_consolidados, ignore_index=True)
                        ruta_cons = Path(salida) / "archivos_consolidados.csv"
                        df_final.to_csv(ruta_cons, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
                        tamanio = os.path.getsize(ruta_cons) / 1024
                        self._log(f"    [OK] Consolidado guardado con exito.")
                        self._log(f"    Archivo   : archivos_consolidados.csv")
                        self._log(f"    Encoding  : {EXPORT_ENCODING}")
                        self._log(f"    Separator : {EXPORT_SEP}")
                        self._log(f"    Ruta      : {ruta_cons}")
                        self._log(f"    Tamaño    : {tamanio:.1f} KB")
                        self._log(f"    Filas     : {len(df_final):,}")
                        self._log(f"    Columnas  : {len(df_final.columns)}")
                        
                        # Tambien generamos esquema del archivo consolidado
                        generar_reporte_esquema(df_final, "archivos_consolidados.csv", self._log_schema)
                    except Exception as e:
                        self._log(f"    [ERROR] Fallo al consolidar los archivos: {e}")

                self._log(f"\n[OK] Proceso de {accion.upper()} finalizado.")
                
                # Si fue solo analisis, cambiar automaticamente a la pestaña de estructura
                if accion == "analizar":
                    self.after(0, lambda: self._switch_tab(1))
                
            except Exception as e:
                self._log(f"\n[ERROR] Ocurrio un error inesperado: {e}")
            finally:
                self.after(0, lambda: self.btn_analizar.config(state="normal"))
                self.after(0, lambda: self.btn_norm.config(state="normal"))
                self.after(0, lambda: self.status.config(text="Listo", fg="#3fb950"))

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
