import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import os
import csv
import chardet
from collections import Counter
import threading

# Configuración visual moderna
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class CsvApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("CSV Doctor & Consolidator")
        self.geometry("900x650")

        # Variables de estado
        self.selected_files = []
        self.analysis_results = {} # Guardará info de encoding/separador
        self.output_folder = os.path.join(os.path.expanduser("~"), "Desktop", "csv_limpios")

        #Layout principal (Grid 2 columnas)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR (Izquierda) ===
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="CSV TOOL", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Botón 1: Seleccionar
        self.btn_select = ctk.CTkButton(self.sidebar_frame, text="1. Seleccionar CSVs", command=self.select_files)
        self.btn_select.grid(row=1, column=0, padx=20, pady=10)

        # Botón 2: Diagnosticar
        self.btn_diagnose = ctk.CTkButton(self.sidebar_frame, text="2. Diagnosticar", command=self.run_diagnosis_thread, fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"))
        self.btn_diagnose.grid(row=2, column=0, padx=20, pady=10)
        self.btn_diagnose.configure(state="disabled")

        # Botón 3: Consolidar
        self.btn_consolidate = ctk.CTkButton(self.sidebar_frame, text="3. Consolidar", command=self.run_consolidation_thread, fg_color="#2CC985", hover_color="#229D68")
        self.btn_consolidate.grid(row=3, column=0, padx=20, pady=10)
        self.btn_consolidate.configure(state="disabled")

        # === AREA PRINCIPAL (Derecha) ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Etiqueta de estado
        self.lbl_status = ctk.CTkLabel(self.main_frame, text="Seleccione archivos para comenzar...", anchor="w")
        self.lbl_status.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Caja de texto para logs/resultados
        self.textbox = ctk.CTkTextbox(self.main_frame, font=("Consolas", 12))
        self.textbox.grid(row=1, column=0, sticky="nsew")
        self.textbox.insert("0.0", "Esperando archivos...\n")
        self.textbox.configure(state="disabled")

        # Barra de progreso (indeterminada)
        self.progressbar = ctk.CTkProgressBar(self.main_frame)
        self.progressbar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.progressbar.set(0)

    # ==========================================
    # LÓGICA DE INTERFAZ
    # ==========================================

    def log(self, message, error=False):
        self.textbox.configure(state="normal")
        tag = "ERROR" if error else "INFO"
        self.textbox.insert("end", f"[{tag}] {message}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Archivos CSV", "*.csv")])
        if files:
            self.selected_files = list(files)
            self.log(f"Se han seleccionado {len(files)} archivos.")
            self.lbl_status.configure(text=f"{len(files)} archivos listos para diagnosticar.")
            self.btn_diagnose.configure(state="normal")
            self.btn_consolidate.configure(state="disabled")
            self.progressbar.set(0)

    # ==========================================
    # LÓGICA DE DIAGNÓSTICO (Tu script 2 adaptado)
    # ==========================================
    
    def run_diagnosis_thread(self):
        # Ejecutar en hilo separado para no congelar la UI
        self.progressbar.start()
        threading.Thread(target=self.diagnosticar_archivos, daemon=True).start()

    def detect_encoding(self, path):
        with open(path, "rb") as f:
            raw = f.read(100_000)
        enc = chardet.detect(raw)
        return enc["encoding"] or "utf-8"

    def detect_separator(self, path, encoding):
        separadores = [",", ";", "|", "\t"]
        try:
            with open(path, encoding=encoding, errors="replace", newline="") as f:
                muestra = "".join([f.readline() for _ in range(20)])
            dialect = csv.Sniffer().sniff(muestra, delimiters=separadores)
            return dialect.delimiter
        except:
            return "," # Fallback

    def diagnosticar_archivos(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("0.0", "end")
        self.textbox.configure(state="disabled")
        
        self.log("=== INICIANDO DIAGNÓSTICO ===")
        self.analysis_results = {}
        archivos_validos = 0

        for path in self.selected_files:
            nombre = os.path.basename(path)
            self.log(f"Analizando: {nombre}...")
            
            # 1. Encoding
            encoding = self.detect_encoding(path)
            
            # 2. Separador
            sep = self.detect_separator(path, encoding)
            
            # 3. Estructura
            es_valido = True
            msg_validacion = "OK"
            
            try:
                with open(path, encoding=encoding, errors="replace", newline="") as f:
                    reader = csv.reader(f, delimiter=sep, quotechar='"')
                    longitudes = Counter()
                    for i, fila in enumerate(reader, start=1):
                        longitudes[len(fila)] += 1
                
                if len(longitudes) > 1:
                    es_valido = False
                    detalles = ", ".join([f"{cols} cols ({cant} filas)" for cols, cant in longitudes.items()])
                    msg_validacion = f"INCONSISTENTE: {detalles}"
                    self.log(f"⚠ {nombre} -> {msg_validacion}", error=True)
                else:
                    cols = list(longitudes.keys())[0] if longitudes else 0
                    msg_validacion = f"Estructura Válida ({cols} columnas)"
                    self.log(f"✔ {nombre} -> {encoding} | Sep: '{sep}' | {msg_validacion}")

            except Exception as e:
                es_valido = False
                msg_validacion = f"ERROR DE LECTURA: {str(e)}"
                self.log(f"❌ {nombre} -> {msg_validacion}", error=True)

            # Guardamos resultado para usar en consolidación
            self.analysis_results[path] = {
                "encoding": encoding,
                "sep": sep,
                "valido": es_valido
            }
            if es_valido: archivos_validos += 1

        self.progressbar.stop()
        self.progressbar.set(1)
        self.log("="*40)
        self.log(f"Diagnóstico finalizado. {archivos_validos}/{len(self.selected_files)} aptos para consolidar.")
        
        if archivos_validos > 0:
            self.btn_consolidate.configure(state="normal")
            self.lbl_status.configure(text="Diagnóstico completo. Revise los resultados y consolide.")
        else:
            self.lbl_status.configure(text="No hay archivos válidos para consolidar.")

    # ==========================================
    # LÓGICA DE CONSOLIDACIÓN (Tu script 1 adaptado)
    # ==========================================

    def run_consolidation_thread(self):
        self.progressbar.start()
        threading.Thread(target=self.consolidar_archivos, daemon=True).start()

    def normalizar_columnas(self, df):
        df.columns = (
            df.columns
              .str.strip()
              .str.lower()
              .str.replace(" ", "_")
        )
        return df

    def consolidar_archivos(self):
        self.log("\n=== INICIANDO CONSOLIDACIÓN ===")
        dfs = []
        
        # Crear carpeta de salida en escritorio si no existe
        os.makedirs(self.output_folder, exist_ok=True)
        
        for path, info in self.analysis_results.items():
            if not info["valido"]:
                self.log(f"Saltando {os.path.basename(path)} (Inválido)", error=True)
                continue
            
            try:
                # Usamos encoding y sep detectados previamente
                df = pd.read_csv(
                    path,
                    sep=info["sep"],
                    encoding=info["encoding"],
                    dtype=str,
                    engine="python",
                    on_bad_lines="skip"
                )
                df = self.normalizar_columnas(df)
                
                # Añadir columna de origen para trazabilidad (opcional pero útil)
                df["source_file"] = os.path.basename(path)
                
                dfs.append(df)
                self.log(f"Procesado: {os.path.basename(path)}")
                
            except Exception as e:
                self.log(f"Error procesando {os.path.basename(path)}: {e}", error=True)

        if dfs:
            self.log("Concatenando DataFrames...")
            try:
                df_final = pd.concat(dfs, ignore_index=True)
                
                archivo_salida = os.path.join(self.output_folder, "consolidado_normalizado.csv")
                
                df_final.to_csv(
                    archivo_salida,
                    sep=";",
                    encoding="utf-8-sig",
                    index=False,
                    quoting=csv.QUOTE_ALL
                )
                
                self.log(f"✔ ÉXITO. Archivo guardado en:\n{archivo_salida}")
                self.log(f"Total filas: {len(df_final)} | Columnas: {len(df_final.columns)}")
                
                # Abrir carpeta automáticamente al terminar (opcional)
                os.startfile(self.output_folder)
                self.lbl_status.configure(text="Consolidación terminada con éxito.")
                
            except Exception as e:
                self.log(f"Error al guardar consolidado: {e}", error=True)
        else:
            self.log("No se generó ningún DataFrame válido.", error=True)

        self.progressbar.stop()
        self.progressbar.set(1)

if __name__ == "__main__":
    app = CsvApp()
    app.mainloop()