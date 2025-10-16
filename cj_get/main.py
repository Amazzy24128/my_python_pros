from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import os
import time
import signal
from urllib.parse import urlparse, urljoin
from selenium.common.exceptions import TimeoutException
from shutil import which

SAVE_FILE = "/home/amz/文档/my_python_pros/cj_get/cangjie_docs_markdown/all_docs.md"
visited_urls = set()

def setup_driver():
    """配置 Chrome 浏览器"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver_path = which("chromedriver")
    if driver_path:
        print(f"🔧 使用: {driver_path}")
        service = Service(driver_path)
        service.log_path = os.devnull
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(3)
    return driver

def get_page_content(driver, url):
    """获取页面内容"""
    try:
        print(f"📄 正在加载: {url}")
        driver.get(url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        time.sleep(2)  # 等待 JavaScript 执行
        
        return driver.page_source
    except TimeoutException:
        print(f"⏱️ 加载超时")
        return driver.page_source
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        return None

def extract_doc_links(driver, current_url):
    """提取文档链接"""
    links = set()
    base_domain = "docs.cangjie-lang.cn"
    
    try:
        # 获取所有链接
        link_elements = driver.find_elements(By.TAG_NAME, "a")
        
        for element in link_elements:
            try:
                href = element.get_attribute('href')
                if not href:
                    continue
                
                # 只保留同域名下的 HTML 文档链接
                if base_domain in href and href.endswith('.html'):
                    if href not in visited_urls:
                        links.add(href)
                # 处理相对路径
                elif href.endswith('.html') and not href.startswith('http'):
                    full_url = urljoin(current_url, href)
                    if base_domain in full_url and full_url not in visited_urls:
                        links.add(full_url)
            except:
                continue
        
        # 使用 BeautifulSoup 补充提取
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            if href.endswith('.html'):
                if href.startswith('http') and base_domain in href:
                    if href not in visited_urls:
                        links.add(href)
                elif not href.startswith('http'):
                    full_url = urljoin(current_url, href)
                    if base_domain in full_url and full_url not in visited_urls:
                        links.add(full_url)
        
        print(f"   ✅ 提取到 {len(links)} 个新链接")
        
    except Exception as e:
        print(f"⚠️ 提取链接失败: {e}")
    
    return list(links)

def html_to_markdown(html, url):
    """将 HTML 转换为 Markdown"""
    soup = BeautifulSoup(html, "html.parser")
    
    # 移除无用标签
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'noscript', 'svg']):
        tag.decompose()
    
    # 移除导航元素
    for selector in ['.sidebar', '.menu', '.navigation', '.header', '.footer', '.toctree-wrapper']:
        for element in soup.select(selector):
            element.decompose()
    
    # 查找主要内容
    main_content = None
    selectors = [
        '[role="main"]',
        'main',
        'article',
        '.document',
        '.content',
        '.body',
        '.rst-content',
        '#main-content'
    ]
    
    for selector in selectors:
        main_content = soup.select_one(selector)
        if main_content:
            print(f"   ✓ 找到内容: {selector}")
            break
    
    if not main_content:
        main_content = soup.body if soup.body else soup
        print("   ⚠ 使用 body")
    
    # 转换为 Markdown
    markdown_content = md(
        str(main_content),
        heading_style="ATX",
        bullets="-",
        code_language="cangjie",
        strip=['img', 'svg']
    )
    
    # 清理多余空行
    lines = []
    prev_empty = False
    for line in markdown_content.split('\n'):
        is_empty = not line.strip()
        if is_empty and prev_empty:
            continue
        lines.append(line)
        prev_empty = is_empty
    
    markdown_content = '\n'.join(lines).strip()
    
    # 添加标题和来源
    title = soup.find('title')
    if title:
        title_text = title.get_text().strip()
        markdown_content = f"# {title_text}\n\n> 来源: {url}\n\n{markdown_content}"
    
    return markdown_content

def save_markdown_to_file(markdown_content):
    """将 Markdown 内容追加到单一文件"""
    os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
    with open(SAVE_FILE, "a", encoding="utf-8") as f:
        f.write(markdown_content + "\n\n")
    print(f"✅ 已追加内容到 {SAVE_FILE}")

def crawl_page(driver, url):
    """爬取单个页面"""
    if url in visited_urls:
        return []
    
    visited_urls.add(url)
    
    html = get_page_content(driver, url)
    if not html:
        return []
    
    markdown_content = html_to_markdown(html, url)
    if len(markdown_content.strip()) > 100:  # 只保存有效内容
        save_markdown_to_file(markdown_content)
    
    return extract_doc_links(driver, url)

def safe_quit_driver(driver):
    """安全关闭浏览器"""
    try:
        driver.quit()
    except:
        try:
            if hasattr(driver.service, 'process') and driver.service.process:
                os.kill(driver.service.process.pid, signal.SIGKILL)
        except:
            pass

def main():
    """主函数"""
    print("=" * 70)
    print("🚀 仓颉编程语言文档爬虫 (所有内容追加到一个文件)")
    print("=" * 70)
    print(f"📁 保存位置: {SAVE_FILE}\n")
    
    driver = None
    try:
        driver = setup_driver()
        
        # 直接从文档站点开始爬取
        start_urls = [
            "https://docs.cangjie-lang.cn/docs/1.0.3/user_manual/source_zh_cn/first_understanding/hello_world.html",
            # 可以添加更多入口
            "https://docs.cangjie-lang.cn/docs/1.0.3/user_manual/source_zh_cn/index.html",
        ]
        
        queue = start_urls.copy()
        max_pages = 500  # 增加爬取数量
        
        print(f"🎯 起始页面数: {len(start_urls)}")
        print(f"📊 最大爬取数: {max_pages}\n")
        
        while queue and len(visited_urls) < max_pages:
            current_url = queue.pop(0)
            
            print(f"\n{'='*70}")
            print(f"📊 进度: {len(visited_urls)}/{max_pages}")
            
            new_links = crawl_page(driver, current_url)
            
            for link in new_links:
                if link not in visited_urls and link not in queue:
                    queue.append(link)
            
            print(f"   队列剩余: {len(queue)} 个")
            time.sleep(1)  # 避免请求过快
        
        print(f"\n{'='*70}")
        print(f"✨ 爬取完成！")
        print(f"📊 共爬取 {len(visited_urls)} 个页面")
        print(f"📂 保存位置: {SAVE_FILE}")
        print(f"{'='*70}")
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ 用户中断，已爬取 {len(visited_urls)} 个页面")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            safe_quit_driver(driver)
            print("🔒 浏览器已关闭")

if __name__ == "__main__":
    main()