import sys
from playwright.sync_api import sync_playwright

def inspect_page():
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            if not contexts:
                print("No contexts found.")
                return
            context = contexts[0]
            pages = context.pages
            if not pages:
                print("No pages found.")
                return
            
            # Find the tableau page
            tableau_page = None
            for page in pages:
                print(f"Open page: {page.title()} - {page.url}")
                if "tableau.com" in page.url:
                    tableau_page = page
                    break
            
            if not tableau_page:
                print("Could not find a Tableau page.")
                return
            
            print("\n--- Inspecting Tableau Page ---")
            print("Title:", tableau_page.title())
            print("URL:", tableau_page.url)
            
            frames = tableau_page.frames
            print(f"Found {len(frames)} frames.")
            for i, frame in enumerate(frames):
                print(f"  Frame {i}: name='{frame.name}', url='{frame.url}'")
            
            # Check for common selectors
            selectors = [
                "tableau-viz", "#tableau-viz", ".tab-storyboard", 
                "[data-tb-test-id='DesktopLayout']", ".tabCanvas", ".vizContainer",
                "iframe"
            ]
            
            print("\nChecking for selectors in main page:")
            for sel in selectors:
                count = len(tableau_page.locator(sel).element_handles())
                print(f"  {sel}: {count}")
                
            print("\nChecking for selectors in all frames:")
            for sel in selectors:
                count = sum(len(f.locator(sel).element_handles()) for f in frames)
                print(f"  {sel}: {count}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    inspect_page()
