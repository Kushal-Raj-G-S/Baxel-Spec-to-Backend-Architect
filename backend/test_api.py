import time
import subprocess
import requests
import sys
import os

def run_test():
    print("=== Baxel Backend End-to-End Test ===")
    
    # 1. Start the uvicorn server in a subprocess
    # Run from the backend directory using the venv python executable
    venv_python = os.path.join("venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = "python" # fallback
        
    print("Starting Uvicorn server...")
    server_process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    )
    
    # Wait for server to start
    time.sleep(3.0)
    
    # Check if server is running
    if server_process.poll() is not None:
        print("Error: Uvicorn server failed to start.")
        sys.exit(1)
        
    print("Server started successfully.")
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        # Test 1: Check root endpoint
        print("\nTesting root endpoint...")
        res = requests.get(f"{base_url}/")
        print("Root response:", res.json())
        assert res.status_code == 200
        
        # Test 2: Generate architecture spec (Phase 1, 2, 3 trigger)
        print("\nTriggering architecture generation...")
        payload = {
            "prompt": "I want to build a real-time collaborative workspace where users edit documents together.",
            "parent_spec_id": None
        }
        res = requests.post(f"{base_url}/api/generate", json=payload)
        print("Generate response:", res.json())
        assert res.status_code == 200
        data = res.json()
        spec_id = data["spec_id"]
        
        # Test 3: Poll status until complete (increased range for cold-start model downloads)
        print(f"\nPolling status for spec {spec_id}...")
        completed = False
        for i in range(300):
            res = requests.get(f"{base_url}/api/status/{spec_id}")
            status_data = res.json()
            print(f"Poll #{i+1} status: {status_data['status']} | Stage: {status_data['current_stage']}")
            
            if status_data["status"] == "completed":
                completed = True
                print("\nGeneration completed! Sample ERD tables:")
                tables = status_data["result"]["database"]["tables"]
                for t in tables:
                    print(f"- Table: {t['name']} ({t['description']})")
                break
            elif status_data["status"] == "failed":
                print("Generation failed:", status_data.get("error"))
                break
                
            time.sleep(1.0)
            
        assert completed, "Generation did not complete in time"
        
        # Test 4: Verify DB persistence (SQLite file exists)
        print("\nChecking database persistence...")
        # Since SQLite is config-backed, verify baxel.db was created in workspace
        db_path = "../baxel.db"
        if os.path.exists(db_path):
            print(f"Success: SQLite database file found at {os.path.abspath(db_path)}.")
        else:
            print("Warning: local SQLite file baxel.db was not found in expected folder. (If using PostgreSQL, this is normal).")
            
        # Test 5: Chat with the generated specification (Phase 4 / Chatbot context)
        print("\nTesting Chatbot feature (General Business query)...")
        chat_payload = {
            "message": "What is the recommended database and caching setup for this workspace?",
            "spec_id": spec_id
        }
        res = requests.post(f"{base_url}/api/chat", json=chat_payload)
        print("Chat response (Business):", res.json()["reply"])
        assert res.status_code == 200
        
        print("\nTesting Chatbot feature (Technical Query)...")
        chat_payload = {
            "message": "Show me the database schema for the tables and scale details.",
            "spec_id": spec_id
        }
        res = requests.post(f"{base_url}/api/chat", json=chat_payload)
        print("Chat response (Technical):", res.json()["reply"])
        assert res.status_code == 200
        
        print("\n=== All Tests Passed Successfully! ===")
        
    finally:
        print("\nStopping server process...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    run_test()
