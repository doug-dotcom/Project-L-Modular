# ============================================================
# SHINE L COMPATIBILITY SHIM
# Keeps old imports alive during modular transition.
# ============================================================

def compatibility_status():
    return {
        "status": "online",
        "mode": "modular_compatibility",
        "server_py_role": "legacy host / compatibility bridge",
        "api_main_role": "primary app entrypoint",
        "memory_runtime": "local_json_first",
        "supabase_role": "protected_backup_sync_layer"
    }
