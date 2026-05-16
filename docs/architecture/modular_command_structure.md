# Shine L Modular Command Structure

## Doctrine

Doug
↓
Lieutenant Colonel L
↓
Major Tegan Triage
↓
Captains
↓
Lieutenants
↓
Soldiers / Resources

## Migration Rule

Copy first.
Test.
Redirect.
Only then remove old code.

## Memory Doctrine

PCG local JSON = operational memory master.
Supabase = cloud backup, sync, and disaster recovery.

No Supabase memory migration occurs until:
- export complete
- count verified
- local backup created
- captain classification plan approved

## Initial Target Folders

api/routes
api/services
core
orchestration
memory/local_json
memory/supabase_sync
memory/captains

## Current Status

Framework created.
server.py untouched.
