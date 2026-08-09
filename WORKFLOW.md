# Default Workflow

Use this repository as the root for new work.

1. Create a new project with `.\scripts\New-Project.ps1 <name>`.
2. Work inside the dated folder it creates, like `YYYY-MM-DD\<name>`.
3. Keep changes in small commits so rollback stays easy.
4. Save a backup with `.\scripts\Backup-Workspace.ps1` whenever you want a checkpoint.
5. Use Git history for undoing work, not ad hoc copies.

If you need a different date bucket, pass `-Date yyyy-MM-dd` to the script.

This keeps future projects in one Git repository, which makes revert and review much easier.
