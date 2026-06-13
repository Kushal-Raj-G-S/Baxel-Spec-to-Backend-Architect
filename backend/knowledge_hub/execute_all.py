import sys
import subprocess
from pathlib import Path

def main():
    hub_dir = Path(__file__).parent.resolve()
    py_files = sorted(list(hub_dir.glob("*.py")))
    
    # Exclude system/master runner scripts
    excluded = {
        Path(__file__).name,
        "modify_all.py",
        "run_knowledge_builder.py"
    }
    
    scripts_to_run = [f for f in py_files if f.name not in excluded]
    
    print("=====================================================")
    # Print list of scripts to execute
    print(f"Found {len(scripts_to_run)} model scripts to run:")
    for idx, s in enumerate(scripts_to_run):
        print(f"  [{idx+1:02d}] {s.name}")
    print("=====================================================")
    
    # Execute the backend python venv
    venv_python = Path(__file__).parents[1] / "venv" / "Scripts" / "python.exe"
    python_cmd = str(venv_python) if venv_python.exists() else "python"
    
    success_count = 0
    failure_count = 0
    
    for idx, script in enumerate(scripts_to_run):
        print(f"\n[Running {idx+1}/{len(scripts_to_run)}] Executing {script.name}...")
        try:
            # Run the script and stream the output to console
            result = subprocess.run(
                [python_cmd, str(script)],
                cwd=str(hub_dir.parent),  # run from backend/ folder context
                text=True
            )
            if result.returncode == 0:
                print(f"  [SUCCESS] {script.name} completed successfully.")
                success_count += 1
            else:
                print(f"  [FAILED] {script.name} failed with return code {result.returncode}.")
                failure_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to run {script.name}: {e}")
            failure_count += 1
            
    print("\n=====================================================")
    print("=== Execution Complete ===")
    print(f"Success: {success_count} / {len(scripts_to_run)}")
    print(f"Failed: {failure_count} / {len(scripts_to_run)}")
    print("=====================================================")

if __name__ == "__main__":
    main()
