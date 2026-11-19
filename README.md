# Aphynador

**Afinador histórico en tiempo real para instrumentos de teclado antiguo** (clavecinos, órganos de tubos, clavicordios y fortepianos), diseñado con una arquitectura desacoplada y multiplataforma preparada para escritorio (Linux, Windows, macOS) y dispositivos móviles (Android e iOS).

---

## Características Principales

* **Motor de Detección Fundamental ($f_0$) de Alta Precisión:** Implementa el algoritmo **YIN** con interpolación parabólica sub-muestra, filtro paso-bajo y estabilizador de mediana temporal para evitar saltos erróneos de octava o quinta en timbres muy ricos en armónicos superiores.
* **Biblioteca de Temperamentos Históricos y Temperamento Igual:**
  * Temperamento Igual (`12-TET`), Mesotónico de $1/4$ de Coma, Werckmeister III, Vallotti y Kirnberger III.
  * Formato abierto y modular (**1 archivo `.json` por temperamento**) con fichas didácticas multiidioma, análisis armónico de las 12 tríadas mayores (detección automática de terceras mayores puras $5/4$ y quinta del lobo) y secuencias de partición.
  * Importación y exportación compatible con el estándar internacional **Scala (`.scl`)**, además de un editor visual integrado.
* **Medidor Analógico Balístico Dual (Flet Canvas):**
  * **Modo `AUTO` ($\pm 50\,\text{cents}$):** Escala lineal de alta precisión alrededor de la nota detectada.
  * **Modo `MANUAL` ($\pm 500\,\text{cents}$):** Escala comprimida no lineal de $\pm 5$ semitonos (inspirada en medidores orquestales como el Korg OT-120) ideal para subidas generales de afinación (*pitch raise*) y notas graves.
* **Lectura Triple Simultánea:**
  * Desviación en **cents** ($\Delta c = 1200 \cdot \log_2(f / f_{\text{target}})$).
  * Equivalencia en **fracciones de coma** (Coma Sintónica $\text{CS} \approx 21.51\,\text{c}$ y Coma Pitagórica $\text{CP} \approx 23.46\,\text{c}$).
  * **Velocidad de batimentos ($\text{bat/s}$)** calculada entre los armónicos coincidentes ($|n \cdot f_1 - m \cdot f_2|$) respecto a una nota de referencia configurable.
* **Generador de Tonos de Referencia (Feedback Sonoro):** Sintetizador en tiempo real con acumulador de fase continuo, envolvente suave *Attack/Release* (sin chasquidos) y selector de formas de onda (*Senoidal, Triangular, Diente de sierra, Órgano Principal $8'+4'$* y *Clavecín*).
* **Herramientas Especializadas:**
  * **Asistente Interactivo de Partición:** Guía paso a paso para sentar la partición en la octava central con validación automática por estabilidad.
  * **Calibración *Match Pitch*:** Calcula la frecuencia base $A_4$ efectiva a partir de la medición de un tubo o cuerda fija de referencia.
  * **Compensación de Inarmonicidad ($B$):** Ajuste progresivo de estiramiento de octava para instrumentos de cuerda corta y gruesa.
* **Temas (*Skins*) e Internacionalización (`i18n`):** Soporte para temas Claro, Oscuro y Sistema, así como importación dinámica de archivos de traducción en JSON.

---

## Arquitectura del Proyecto

El código está dividido en capas estrictamente aisladas para garantizar una interfaz fluida sin bloqueos y facilitar la compilación nativa en dispositivos móviles:

```text
aphynador/
├── core/                      # Lógica acústica y de negocio pura (0 dependencias de UI/audio)
│   ├── acoustics.py           # Cents, comas, modos Auto/Manual, batimentos, Match Pitch, inarmonicidad
│   ├── temperaments.py        # Gestor de biblioteca JSON, constructor por quintas y soporte Scala (.scl)
│   ├── key_analysis.py        # Evaluación armónica de terceras puras y quintas del lobo
│   ├── partition.py           # Asistente interactivo paso a paso para la octava central
│   ├── i18n.py                # Internacionalización dinámica e importación de idiomas
│   ├── entitlements.py        # Gestión centralizada de permisos (ediciones Free y Pro)
│   └── climate.py             # Interfaz extensible para registros climáticos (manual / API / BLE)
├── audio/                     # Procesamiento DSP y síntesis en tiempo real
│   ├── detector.py            # Detector fundamental YIN + estabilizador temporal
│   ├── synthesizer.py         # Oscilador multi-onda con fase continua y envolvente ADSR
│   └── engine.py              # Motor dúplex sin bloqueos con instantáneas atómicas
├── ui/                        # Interfaz gráfica multiplataforma en Flet
│   ├── compat.py              # Capa de compatibilidad entre versiones de Flet
│   ├── theme.py               # Paletas Claro, Oscuro y Sistema
│   ├── needle_gauge.py        # Cuadrante analógico dual con física masa-resorte-amortiguador
│   └── views/                 # Vistas: Afinador, Biblioteca/Editor y Ajustes
├── data/
│   ├── temperaments/          # Archivos .json individuales por temperamento
│   └── locales/               # Archivos de traducción (es.json, en.json)
├── tests/                     # Batería de pruebas unitarias (pytest)
├── main.py                    # Punto de entrada de la aplicación
└── pyproject.toml             # Metadatos y dependencias del proyecto
```

---

## Requisitos e Instalación

### 1. Dependencias del sistema (Linux / Debian / Ubuntu)
Si trabajas en Linux, asegúrate de contar con `libportaudio2` para la captura y reproducción de audio:

```bash
sudo apt update && sudo apt install -y libportaudio2
```

### 2. Clonar el repositorio y crear el entorno virtual

```bash
git clone https://github.com/sircederik/aphynador.git
cd aphynador
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Ejecución y Pruebas

### Ejecutar la batería de pruebas unitarias
Verifica los cálculos acústicos, el formato Scala (`.scl`), el detector YIN, el sintetizador y la física de la aguja:

```bash
python -m pytest -v
```

### Iniciar la aplicación de escritorio

```bash
python main.py
```

---

## Hoja de Ruta (Roadmap)

* [x] **Hito 1:** Núcleo matemático (`core/`), esquema modular JSON, soporte Scala (`.scl`), asistente de partición e internacionalización.
* [x] **Hito 2:** Motor de audio dúplex en tiempo real con algoritmo YIN y sintetizador multi-onda sin chasquidos.
* [x] **Hito 3:** Interfaz gráfica multiplataforma en Flet con aguja analógica balística (`AUTO`/`MANUAL`), temas, ficha didáctica y editor.
* [ ] **Hito 4:** Bitácora histórica en SQLite con registro de condiciones climáticas por instrumento y motor estadístico de diagnóstico y mantenimiento.
* [ ] **Hito 5:** Empaquetado nativo para Android (`.apk` / `.aab`) e iOS (`.ipa`).

---

## Licencia

Proyecto desarrollado por [@sircederik](https://github.com/sircederik).