# nxnative-oot (Fork para Apple Silicon)

Fork de nxnative con parches y optimizaciones para ejecutar **The Legend of Zelda: Ocarina of Time** (`0400486024DEC000`, v131072) en macOS / Apple Silicon.

> [!NOTE]
> - Todo este fork, sus parches y documentación fueron generados con asistencia de **Inteligencia Artificial Generativa**.
> - Ha sido probado y verificado en una **MacBook Pro M1 Pro (32 GB RAM)**. No se sabe cómo funcionará en el resto de dispositivos o configuraciones.
> - **En caso de sugerencias o mejoras, por favor no envíen ninguna PR**: este repositorio está pensado únicamente como una base lista para quien quiera compilar y jugar directamente.

---

## Cambios agregados

1. **Objetivo a 60 FPS sin cámara lenta (Frame Pacing y Delta-Time Dinámico)**:
   - Parche en el ratio de simulación del motor (`main+0x6e6cc4`) mediante `MATCH_FRAME_STEP` y `DM_FRAME_DELTA`.
   - Si los milisegundos de GPU superan 16.6 ms (caídas de fotogramas en escenas pesadas), la física avanza en tiempo real en lugar de ralentizarse en cámara lenta.
   - Activado `fps_payback on` y objetivo de 60 FPS por defecto.

2. **Eliminación de glitches gráficos (Esquina verde y texturas parpadeantes)**:
   - Configuración de barreras completas de sincronización (`draw_barriers full` en `game.tsv`) para evitar condiciones de carrera en Metal 4.

3. **Corrección de crash al tocar notas de la Ocarina**:
   - Implementado hook `IsOunceVibrationDeviceMounted` en `hle_hid.c` para evitar el aborto de la aplicación al reproducir notas musicales con la Ocarina.

4. **Optimización de cinemáticas y vídeos (Bypass NDVE)**:
   - Parche en `patches.py` que redirige el reproductor de vídeo para saltarse la red neuronal tensorial Ampere no nativa, logrando 60 FPS estables en la pantalla de título y cinemáticas.

5. **Resolución dinámica y escalado MetalFX**:
   - Compatibilidad con escalado MetalFX y limitador de escala de render (`DM_RENDER_SCALE`).

> [!TIP]
> **Detalle sobre las texturas (suelo / agua / río)**:  
> Si en la primera ejecución tras compilar o al entrar a una nueva zona notas alguna textura plana (por ejemplo, el lecho del río o el suelo sin detalle), **basta con cerrar completamente la aplicación y volver a abrirla**; en el siguiente inicio las texturas y shaders cargan de forma correcta y persistente.

---

## Proceso de compilación paso a paso

Para compilar el juego desde cero necesitas el contenedor del juego (`.nup` o `.nsp`) y tu archivo de claves `prod.keys`.

### 1. Requisitos previos

Instalar herramientas de compilación de Xcode:
```bash
xcode-select --install
xcodebuild -downloadComponent MetalToolchain
```

Instalar dependencias mediante [Homebrew](https://brew.sh):
```bash
brew install xcodegen zstd glslang python@3.12
```

Instalar paquetes de Python necesarios:
```bash
python3.12 -m pip install lz4 "capstone>=5,<6" fonttools nsz zbic "backports.zstd; python_version < '3.14'"
```

### 2. Compilar y empaquetar la aplicación Mac

Desde la carpeta raíz del repositorio:
```bash
python3.12 scripts/build_ipa_from_nsp.py "/ruta/al/juego.nup" -k "/ruta/a/prod.keys" --platform mac-app
```
*(Reemplaza `/ruta/al/juego.nup` y `/ruta/a/prod.keys` por las rutas reales de tus archivos).*

El proceso generará la aplicación `.app` lista para ejecutar en macOS.
