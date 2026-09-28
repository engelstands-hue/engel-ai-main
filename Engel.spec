# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all


ENGEL_RUNTIME_TMPDIR = os.path.abspath(os.path.join(os.getcwd(), 'runtime', 'pyinstaller_tmp'))
os.makedirs(ENGEL_RUNTIME_TMPDIR, exist_ok=True)

pyside6_d,   pyside6_b,   pyside6_h   = collect_all('PySide6')
shiboken6_d, shiboken6_b, shiboken6_h = collect_all('shiboken6')
playwright_d, playwright_b, playwright_h = collect_all('playwright')
requests_d,  requests_b,  requests_h  = collect_all('requests')
httpx_d,     httpx_b,     httpx_h     = collect_all('httpx')
psutil_d,    psutil_b,    psutil_h    = collect_all('psutil')
numpy_d,     numpy_b,     numpy_h     = collect_all('numpy')

new_engel_ai_datas = [
    # Wave 1 (original)
    ('engel_agent_main', 'engel_agent_main'),
    ('engel3d_office_main', 'engel3d_office_main'),
    ('engelsandbox_main', 'engelsandbox_main'),
    # Wave 2 (small vendored folders <50MB)
    ('engel_cli_anything_main', 'engel_cli_anything_main'),
    ('engel_git_nexus_main', 'engel_git_nexus_main'),
    ('engel_open_agents_main', 'engel_open_agents_main'),
    ('engel_airllm_main', 'engel_airllm_main'),
    ('engel_chat_ui_main', 'engel_chat_ui_main'),
    ('engel_cluster_main', 'engel_cluster_main'),
    ('engel_knowledge_graph_v2_main', 'engel_knowledge_graph_v2_main'),
    # Wave 3 (LFM2 family + gstack)
    ('engel_gstack_main', 'engel_gstack_main'),
    ('engel_lfm2_main', 'engel_lfm2_main'),
    ('engel_lfm2_code_review_main', 'engel_lfm2_code_review_main'),
    ('engel_lfm2_mobile_main', 'engel_lfm2_mobile_main'),
    ('engel_lfm2_vision_main', 'engel_lfm2_vision_main'),
    # Wave 4 (Claw3D, CubeSandbox, DarwinEvolver, LocalSend — Hermes too big to bundle)
    ('engel_claw3d_main', 'engel_claw3d_main'),
    ('engel_cubesandbox_main', 'engel_cubesandbox_main'),
    ('engel_darwinian_evolver_main', 'engel_darwinian_evolver_main'),
    ('engel_localsend_main', 'engel_localsend_main'),
]

a = Analysis(
    ['engel_companion.py'],
    pathex=[],
    binaries=pyside6_b + shiboken6_b + playwright_b + psutil_b + numpy_b + requests_b + httpx_b,
    datas=pyside6_d + shiboken6_d + playwright_d + psutil_d + numpy_d + requests_d + httpx_d + new_engel_ai_datas,
    hiddenimports=(
        pyside6_h + shiboken6_h + playwright_h +
        psutil_h + numpy_h + requests_h + httpx_h +
        ['engel_browser_ai_bridge', 'engel_evolver_bridge', 'engel_ephify_bridge',
         'engel_sandbox_bridge', 'engel_jcode_bridge', 'engel_ensor_bridge',
         'engel_ehuman_bridge', 'engel_engize_bridge', 'engel_lokalz_bridge',
         'engel_eng3d_bridge', 'engel_local_llm_bridge', 'engel_discord_bridge',
         'engel_speech_bridge', 'engel_code_workshop',
         'engel_ai', 'engel_ai_update_routes', 'engel_communication_router',
         'engel_agent_bridge', 'engel_engel_agent_runner',
         'engel_engel3d_runner', 'engel_engel_sandbox_runner',
         'engel_wsl_bridge', 'engel_wsl_ubuntu_runner',
         'engel_engelcode_runner', 'engel_engel_main_runner',
         'engel_engel_lan_runner', 'engel_minor_tools_runner',
         'engel_route_explorer', 'engel_ai_connector_hub',
         'engel_saved_skills_list',
         'engel_account_connector',
         'engel_progress_dashboard', 'engel_memory_candidate_inventory',
         'engel_archive_shelf_manager',
         # Wave 2/3/4 runners + Architect Agent + Meeting Room
         'engel_new_tools_runner', 'engel_wave3_runner', 'engel_wave4_runner',
         'engel_architect_agent', 'engel_agent_meetingroom',
         'engel_octogent_runner', 'engel_airllm_bridge',
         'playwright', 'playwright.sync_api', 'discord', 'aiohttp',
         'faster_whisper', 'piper', 'onnxruntime', 'ctranslate2', 'sounddevice',
         'huggingface_hub', 'tokenizers',
         'requests', 'httpx', 'psutil', 'numpy']
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyinstaller_runtime_hooks\\engel_temp_runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Engel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=ENGEL_RUNTIME_TMPDIR,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\branding\\final\\engel_icon_final.ico'],
)
