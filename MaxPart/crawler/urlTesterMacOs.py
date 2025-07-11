import webbrowser
import time
import sys
import termios
import tty

urls = [
    "https://www.w3schools.com",
    "https://openai.com",
    "https://example.com"
]

results = []

def get_single_key():
    """Read one character from stdin without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)  # Read 1 char
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch.lower()

def review_urls(url_list):
    for url in url_list:
        print(f"\nOpening site: {url}")
        webbrowser.open(url)
        time.sleep(2)

        print("🔁 Switch to the terminal to respond (y/n)...")

        while True:
            print("Approve this site? (y/n): ", end='', flush=True)
            key = get_single_key()
            print(key)  # echo keypress
            if key == 'y':
                results.append((url, 1))
                break
            elif key == 'n':
                results.append((url, 0))
                break
            else:
                print(" ❗ Invalid input. Please press 'y' or 'n'.")

        print("✅ You can now close that tab manually.")

    return results

if __name__ == "__main__":
    final = review_urls(urls)
    print("\nReview complete:")
    for url, score in final:
        print(f"{url} => {'Approved' if score else 'Denied'}")
        
        
print(results)