import os
import sys
import subprocess

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bot_path = os.path.join(base_dir, "bot.py")
    
    print("POLVON Somsa Tizimi ishga tushirilmoqda (bot.py orqali)...")
    try:
        subprocess.run([sys.executable, bot_path], check=True)
    except KeyboardInterrupt:
        print("\nTizim to'xtatildi.")
    except Exception as e:
        print(f"\nXatolik yuz berdi: {e}")
