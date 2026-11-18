import subprocess
import os

def sync_databases():
    env = os.environ.copy()
    env["PGPASSWORD"] = "123"
    
    pg_dump_cmd = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        "-h", "localhost",
        "-p", "5433",
        "-U", "postgres",
        "--clean",
        "--if-exists",
        "vkr_knowledge_base"
    ]
    
    psql_cmd = [
        r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "-h", "localhost",
        "-p", "5432",
        "-U", "postgres",
        "vkr_knowledge_base"
    ]
    
    print("Dumping from port 5433 and restoring to port 5432...")
    p1 = subprocess.Popen(pg_dump_cmd, stdout=subprocess.PIPE, env=env)
    p2 = subprocess.Popen(psql_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    p1.stdout.close()
    out, err = p2.communicate()
    print("Restore output code:", p2.returncode)
    if err:
        print("Restore stderr:", err.decode("utf-8", errors="ignore")[:300])

if __name__ == "__main__":
    sync_databases()
