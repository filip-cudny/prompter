"""PyInstaller hook for sounddevice - collects data files and portaudio binaries."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("sounddevice") + collect_data_files("_sounddevice_data")
binaries = collect_dynamic_libs("sounddevice") + collect_dynamic_libs("_sounddevice_data")
