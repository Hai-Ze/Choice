"""
Crawl ToanMath.com - Download PDF exam papers
Phase 1: Scan checkpoint from processed directory
Phase 2: Crawl metadata from website using Playwright
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Set, List, Dict
from urllib.parse import urljoin, urlparse

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Playwright imports
from playwright.async_api import async_playwright, Browser
from bs4 import BeautifulSoup

def scan_processed_directory(processed_path: str) -> Set[str]:
    """
    Scan processed directory and return set of folder names (checkpoint)
    """
    processed_dir = Path(processed_path)

    if not processed_dir.exists():
        print(f"❌ Thư mục {processed_path} không tồn tại")
        return set()

    # Get all folder names in processed directory
    checkpoints = {
        folder.name for folder in processed_dir.iterdir()
        if folder.is_dir() and not folder.name.startswith('.')
    }

    print(f"✅ Found {len(checkpoints)} checkpoints in {processed_path}")
    if checkpoints:
        sorted_checkpoints = sorted(checkpoints, reverse=True)
        print(f"📁 Latest checkpoint: {sorted_checkpoints[0]}")
        print(f"📁 Oldest checkpoint: {sorted_checkpoints[-1]}")

    return checkpoints

def save_checkpoint(checkpoints: Set[str], output_file: str):
    """
    Save checkpoint list to file for later use
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for checkpoint in sorted(checkpoints):
            f.write(f"{checkpoint}\n")
    print(f"💾 Saved checkpoints to {output_file}")

async def phase2_crawl_metadata(base_url: str, output_file: str, checkpoints: Set[str], max_pages: int = 50):
    """
    Phase 2: Crawl metadata from ToanMath.com using Playwright
    Extract: exam names, detail links, PDF download links
    Handle pagination and stop at checkpoint
    """
    print("\n" + "=" * 50)
    print("PHASE 2: Crawl Metadata from Website (Playwright)")
    print("=" * 50)

    results = []
    page_num = 1
    hit_checkpoint = False

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            while page_num <= max_pages and not hit_checkpoint:
                print(f"\n📄 Page {page_num}: {base_url}")

                # Navigate to page
                await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector('.entry-title a', timeout=10000)

                # Extract exam links
                exam_entries = await page.query_selector_all('.entry-title a')
                print(f"✅ Found {len(exam_entries)} exam entries")

                for i, entry in enumerate(exam_entries, 1):
                    # Get exam name and URL
                    exam_name = await entry.evaluate('el => el.textContent.trim()')
                    detail_url = await entry.evaluate('el => el.href')

                    # Generate folder name to check against checkpoints
                    folder_name = detail_url.split('/')[-1].replace('.html', '')

                    # Check if this is a checkpoint (stop condition)
                    if folder_name in checkpoints:
                        print(f"\n🛑 Checkpoint reached: {exam_name}")
                        print(f"   Folder: {folder_name}")
                        print(f"   Stopping crawl as this file is already processed")
                        hit_checkpoint = True
                        break

                    print(f"\n📄 [{page_num}.{i}] Processing: {exam_name}")
                    print(f"   Detail URL: {detail_url}")

                    # Navigate to detail page
                    detail_page = await browser.new_page()
                    try:
                        await detail_page.goto(detail_url, wait_until="networkidle", timeout=30000)

                        # Get HTML and parse with BeautifulSoup
                        html_content = await detail_page.content()
                        soup = BeautifulSoup(html_content, 'html.parser')

                        # Extract PDF link from iframe or link
                        pdf_url = None

                        # Try method 1: Look for iframe with PDF
                        iframe = soup.find('iframe', class_='wonderplugin-pdf-iframe')
                        if iframe and iframe.get('src'):
                            # Extract file parameter from URL
                            src = iframe['src']
                            if 'file=' in src:
                                from urllib.parse import unquote, parse_qs
                                # Parse URL and extract file parameter
                                parsed = urlparse(src)
                                file_param = parse_qs(parsed.query).get('file', [None])[0]
                                if file_param:
                                    pdf_url = unquote(file_param)

                        # Try method 2: Look for download link
                        if not pdf_url:
                            download_link = soup.find('a', class_='pdf-download')
                            if download_link and download_link.get('href'):
                                pdf_url = download_link['href']

                        if pdf_url:
                            print(f"   ✅ PDF Link: {pdf_url}")

                            results.append({
                                'name': exam_name,
                                'detail_url': detail_url,
                                'pdf_url': pdf_url
                            })
                        else:
                            print(f"   ❌ No PDF link found")

                    except Exception as e:
                        print(f"   ❌ Error: {e}")
                    finally:
                        await detail_page.close()

                # Check if we hit checkpoint
                if hit_checkpoint:
                    break

                # Find next page link
                if page_num < max_pages and not hit_checkpoint:
                    try:
                        # Look for next page button (WordPress pagination)
                        next_link = await page.query_selector('a.next')
                        if next_link:
                            base_url = await next_link.evaluate('el => el.href')
                            page_num += 1
                            print(f"\n➡️  Moving to page {page_num}")
                            await page.wait_for_timeout(2000)  # Wait before next page
                        else:
                            print(f"\n✅ No more pages found")
                            break
                    except:
                        print(f"\n✅ No more pages found")
                        break
                else:
                    break

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Saved {len(results)} metadata entries to {output_file}")
    if hit_checkpoint:
        print(f"🛑 Stopped at checkpoint (page {page_num})")
    return results

async def phase3_download_pdfs(metadata_file: str, pdf_dir: str, checkpoints: Set[str]):
    """
    Phase 3: Download PDF files
    Check against checkpoints to stop when reaching processed files
    """
    print("\n" + "=" * 50)
    print("PHASE 3: Download PDF Files")
    print("=" * 50)

    # Load metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        exams = json.load(f)

    print(f"📋 Found {len(exams)} exams to download")

    import aiohttp
    import aiofiles

    pdf_path = Path(pdf_dir)
    pdf_path.mkdir(exist_ok=True)

    downloaded = 0
    skipped = 0

    async with aiohttp.ClientSession() as session:
        for exam in exams:
            exam_name = exam['name']
            pdf_url = exam['pdf_url']

            # Generate folder name from URL (similar to processed folders)
            folder_name = pdf_url.split('/')[-1].replace('.pdf', '')
            pdf_file = pdf_path / f"{folder_name}.pdf"

            # Check if already exists
            if pdf_file.exists():
                print(f"⏭️  Skip: {exam_name} (already exists)")
                skipped += 1
                continue

            # Download PDF
            print(f"📥 Downloading: {exam_name}")
            print(f"   URL: {pdf_url}")
            print(f"   Save to: {pdf_file}")

            try:
                async with session.get(pdf_url) as response:
                    if response.status == 200:
                        content = await response.read()

                        async with aiofiles.open(pdf_file, 'wb') as f:
                            await f.write(content)

                        print(f"   ✅ Downloaded: {len(content)} bytes")
                        downloaded += 1
                    else:
                        print(f"   ❌ Failed: HTTP {response.status}")

            except Exception as e:
                print(f"   ❌ Error: {e}")

    print(f"\n📊 Summary:")
    print(f"   ✅ Downloaded: {downloaded}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   📁 PDFs saved to: {pdf_dir}")

if __name__ == "__main__":
    # Configuration
    BASE_DIR = Path(__file__).parent
    PROCESSED_DIR = BASE_DIR / "processed"
    CHECKPOINT_FILE = BASE_DIR / "checkpoint.txt"
    METADATA_FILE = BASE_DIR / "metadata.json"
    TOANMATH_URL = "https://toanmath.com/de-thi-thu-thpt-mon-toan"

    # Phase 1: Scan and save checkpoint
    print("=" * 50)
    print("PHASE 1: Scan Checkpoint")
    print("=" * 50)

    checkpoints = scan_processed_directory(str(PROCESSED_DIR))
    save_checkpoint(checkpoints, str(CHECKPOINT_FILE))

    # Preview checkpoints
    if checkpoints:
        print(f"\n📋 Preview 5 newest checkpoints:")
        for i, cp in enumerate(sorted(checkpoints, reverse=True)[:5], 1):
            print(f"  {i}. {cp}")

    # Phase 2: Crawl metadata with checkpoint stop
    asyncio.run(phase2_crawl_metadata(TOANMATH_URL, str(METADATA_FILE), checkpoints))

    # Phase 3: Download PDFs
    PDF_DIR = BASE_DIR / "pdf"
    asyncio.run(phase3_download_pdfs(str(METADATA_FILE), str(PDF_DIR), checkpoints))
