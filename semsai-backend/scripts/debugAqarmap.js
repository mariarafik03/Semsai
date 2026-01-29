
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';
import fs from 'fs';

const HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8'
};

async function debugPage() {
    console.log('Fetching page to analyze structure...');
    
    const url = 'https://aqarmap.com.eg/compounds-ratings/ar?page=1';
    const response = await fetch(url, { headers: HEADERS });
    
    console.log(`Status: ${response.status}`);
    
    const html = await response.text();
    console.log(`HTML Length: ${html.length} characters`);
    
    // Save HTML for inspection
    fs.writeFileSync('aqarmap_page_debug.html', html);
    console.log('Saved HTML to: aqarmap_page_debug.html');
    
    const $ = cheerio.load(html);
    
    // Try to find any links
    console.log('\n=== All Links ===');
    $('a').each((i, el) => {
        const href = $(el).attr('href');
        const text = $(el).text().trim();
        if (href && href.includes('compound')) {
            console.log(`Link ${i}: ${text} -> ${href}`);
        }
    });
    
    // Try to find any cards/containers
    console.log('\n=== Potential Card Elements ===');
    $('[class*="card"], [class*="item"], [class*="compound"], [class*="rating"]').each((i, el) => {
        console.log(`Element ${i}: ${$(el).attr('class')}`);
        console.log(`  Text: ${$(el).text().substring(0, 100)}`);
    });
    
    // Check for pagination
    console.log('\n=== Pagination Elements ===');
    $('.pagination, [class*="pag"]').each((i, el) => {
        console.log(`Pagination ${i}: ${$(el).attr('class')}`);
        console.log(`  HTML: ${$(el).html()?.substring(0, 200)}`);
    });
}

debugPage();
