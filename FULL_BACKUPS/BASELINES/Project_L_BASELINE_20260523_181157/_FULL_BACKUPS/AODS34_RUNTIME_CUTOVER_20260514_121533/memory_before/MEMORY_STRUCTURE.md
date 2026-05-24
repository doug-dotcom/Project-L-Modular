# Shine L Memory Structure

## Doctrine

PCG local JSON = operational memory master.
Supabase = cloud backup, sync, and disaster recovery.

## Current Status

AODS 09 created the folder structure only.

No memory migration has occurred.
No Supabase records have been edited.
No runtime memory path has been changed.

## Memory Command Posts

memory/local_json
- future active local memory master

memory/captains
- captain-domain memory files

memory/indexes
- retrieval indexes and classification indexes

memory/backups
- local protected backups

memory/supabase_sync
- sync bridge between PCG and Supabase

memory/imports
- incoming memory dumps

memory/exports
- outgoing verified exports

memory/quarantine
- uncertain or contaminated entries awaiting review

## Critical Rule

Never delete Supabase memory.
Never overwrite the 608-entry archive without verified export and backup.
