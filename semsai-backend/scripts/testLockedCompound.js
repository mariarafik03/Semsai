
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';
import fs from 'fs';

const HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Referer': 'https://aqarmap.com.eg/compounds-ratings/ar'
};

const BASE_URL = 'https://aqarmap.com.eg';

async function testLockedCompound() {
    console.log('🔬 Testing on TRULY LOCKED compound\n');
    
    // First, let's find a locked compound from the main page
    console.log('Step 1: Fetching main page to find locked compounds...');
    const mainPage = await fetch(`${BASE_URL}/compounds-ratings/ar?page=1`, { headers: HEADERS });
    const mainHtml = await mainPage.text();
    const $ = cheerio.load(mainHtml);
    
    // Find compounds marked as closed
    const lockedCompounds = [];
    $('#compoundTable tr, #compoundTableWraper tbody tr').each((i, row) => {
        const $row = $(row);
        const cells = $row.find('td');
        
        if (cells.length >= 4) {
            const compoundId = parseInt($(cells[0]).text().trim());
            const nameCell = $(cells[1]);
            const compoundName = nameCell.find('span').first().text().trim();
            const statusCell = $(cells[4]);
            const statusText = statusCell.text().trim();
            
            if (statusText.includes('مغلق') && compoundId) {
                lockedCompounds.push({
                    id: compoundId,
                    name: compoundName,
                    url: `${BASE_URL}/compounds-ratings/ar/compound/${compoundId}`
                });
            }
        }
    });
    
    console.log(`\nFound ${lockedCompounds.length} locked compounds`);
    console.log('First 5 locked compounds:');
    lockedCompounds.slice(0, 5).forEach(c => {
        console.log(`  - ${c.name} (ID: ${c.id})`);
    });
    
    if (lockedCompounds.length === 0) {
        console.log('\n❌ No locked compounds found!');
        return;
    }
    
    // Test on first locked compound
    const testCompound = lockedCompounds[0];
    console.log(`\n\nStep 2: Testing on: ${testCompound.name} (ID: ${testCompound.id})`);
    console.log(`URL: ${testCompound.url}\n`);
    
    const response = await fetch(testCompound.url, { headers: HEADERS });
    const html = await response.text();
    
    console.log(`✅ Fetched page (${html.length} chars)`);
    
    // Save for inspection
    fs.writeFileSync('locked_compound_page.html', html);
    console.log('💾 Saved to: locked_compound_page.html\n');
    
    const $page = cheerio.load(html);
    
    // Strategy 1: Check for subscription modal content
    console.log('=== Strategy 1: Modal Content Analysis ===');
    const modalText = $page('.modal, [class*="subscription"], [class*="paywall"]').text();
    console.log(`Modal text found: ${modalText.substring(0, 200)}...\n`);
    
    // Strategy 2: Look for hidden/blurred content
    console.log('=== Strategy 2: Hidden Content ===');
    const hiddenContent = $page('[style*="display: none"], [style*="visibility: hidden"], .blur, .blurred').text();
    const ratings = hiddenContent.match(/(\d+\.?\d*)\s*\/\s*10/g);
    console.log(`Hidden ratings found: ${ratings ? ratings.join(', ') : 'None'}\n`);
    
    // Strategy 3: Check page source for embedded data
    console.log('=== Strategy 3: Embedded JSON Data ===');
    const scripts = $page('script').toArray();
    let foundData = false;
    
    for (const script of scripts) {
        const content = $page(script).html() || '';
        
        // Look for rating data in various formats
        if (content.includes('rating') || content.includes('developer') || content.includes('project')) {
            // Try to find JSON objects
            const jsonMatches = content.match(/\{[^{}]*(?:"rating"|"developer"|"project")[^{}]*\}/g);
            if (jsonMatches) {
                console.log(`Found ${jsonMatches.length} potential JSON objects with rating data`);
                jsonMatches.slice(0, 3).forEach((match, idx) => {
                    console.log(`  JSON ${idx + 1}: ${match.substring(0, 100)}...`);
                });
                foundData = true;
                break;
            }
        }
    }
    
    if (!foundData) {
        console.log('No embedded JSON data found\n');
    }
    
    // Strategy 4: Check for data in HTML attributes
    console.log('\n=== Strategy 4: Data Attributes ===');
    const dataElements = $page('[data-rating], [data-score], [data-developer], [data-project]');
    console.log(`Found ${dataElements.length} elements with data attributes`);
    dataElements.each((i, el) => {
        if (i < 5) {
            const attrs = Object.keys($page(el).attr() || {}).filter(k => k.startsWith('data-'));
            console.log(`  Element ${i + 1}: ${attrs.join(', ')}`);
        }
    });
    
    // Strategy 5: Look for API calls in page source
    console.log('\n=== Strategy 5: API Endpoints ===');
    const apiMatches = html.match(/\/api\/[^\s"'<>]+/gi);
    if (apiMatches) {
        const uniqueApis = [...new Set(apiMatches)];
        console.log(`Found ${uniqueApis.length} unique API endpoints:`);
        uniqueApis.slice(0, 5).forEach(api => {
            console.log(`  - ${api}`);
        });
    } else {
        console.log('No API endpoints found');
    }
    
    // Strategy 6: Check all text content for any visible ratings
    console.log('\n=== Strategy 6: All Visible Text ===');
    const allText = $page('body').text();
    const allRatings = allText.match(/(\d+\.?\d*)\s*\/\s*10/g);
    console.log(`All ratings in page text: ${allRatings ? allRatings.join(', ') : 'None'}`);
    
    // Final analysis
    console.log('\n\n📊 ANALYSIS SUMMARY:');
    console.log('='.repeat(50));
    
    const results = {
        compound_id: testCompound.id,
        compound_name: testCompound.name,
        has_modal: modalText.length > 0,
        has_hidden_content: hiddenContent.length > 0,
        has_embedded_json: foundData,
        has_data_attributes: dataElements.length > 0,
        has_api_endpoints: apiMatches && apiMatches.length > 0,
        visible_ratings: allRatings || [],
        extraction_possible: (allRatings && allRatings.length > 0) || foundData
    };
    
    console.log(JSON.stringify(results, null, 2));
    
    fs.writeFileSync('locked_compound_analysis.json', JSON.stringify(results, null, 2));
    console.log('\n💾 Saved analysis to: locked_compound_analysis.json');
}

testLockedCompound();
