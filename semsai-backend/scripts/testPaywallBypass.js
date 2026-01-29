
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://aqarmap.com.eg/compounds-ratings/ar',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin'
};

const BASE_URL = 'https://aqarmap.com.eg';

function randomDelay() {
    const min = 3000;
    const max = 8000;
    return new Promise(resolve => setTimeout(resolve, Math.floor(Math.random() * (max - min + 1)) + min));
}

async function safeFetch(url, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, { headers: HEADERS });
            
            if (response.status === 429) {
                console.log(`   ⚠️ Rate limited. Waiting 30s...`);
                await new Promise(resolve => setTimeout(resolve, 30000));
                continue;
            }
            
            if (response.status === 403) {
                console.log(`   ⚠️ Forbidden (403)`);
                return null;
            }
            
            if (response.status !== 200) {
                if (i < retries - 1) {
                    await randomDelay();
                    continue;
                }
                return null;
            }
            
            return await response.text();
        } catch (error) {
            if (i < retries - 1) await randomDelay();
        }
    }
    return null;
}

// Try multiple strategies to extract ratings from locked pages
async function extractRatingsWithPaywallBypass(html, compoundId, compoundUrl) {
    const $ = cheerio.load(html);
    
    const ratings = {
        compound_id: compoundId,
        developer_rating: {},
        project_rating: {},
        extraction_method: 'none',
        data_completeness: 'locked'
    };
    
    // Strategy 1: Check for embedded JSON data (window.__INITIAL_STATE__ or similar)
    const scripts = $('script').toArray();
    for (const script of scripts) {
        const scriptContent = $(script).html() || '';
        
        // Look for JSON data
        if (scriptContent.includes('__INITIAL_STATE__') || 
            scriptContent.includes('window.data') ||
            scriptContent.includes('ratings')) {
            
            try {
                // Try to extract JSON
                const jsonMatch = scriptContent.match(/\{[^{}]*"rating"[^{}]*\}/g) ||
                                scriptContent.match(/\{[^{}]*"developer"[^{}]*\}/g);
                
                if (jsonMatch) {
                    console.log(`   🔓 Found embedded JSON data`);
                    // Parse and extract ratings
                    for (const match of jsonMatch) {
                        try {
                            const data = JSON.parse(match);
                            if (data.rating || data.developer_rating) {
                                ratings.extraction_method = 'embedded_json';
                                ratings.data_completeness = 'partial';
                                Object.assign(ratings.developer_rating, data.developer_rating || {});
                                Object.assign(ratings.project_rating, data.project_rating || {});
                            }
                        } catch (e) {
                            // Continue trying other matches
                        }
                    }
                }
            } catch (e) {
                // Continue to next strategy
            }
        }
    }
    
    // Strategy 2: Check for data attributes in HTML elements
    const ratingElements = $('[data-rating], [data-score], [data-value]');
    if (ratingElements.length > 0) {
        console.log(`   🔓 Found data attributes`);
        ratingElements.each((i, el) => {
            const $el = $(el);
            const rating = $el.attr('data-rating') || $el.attr('data-score') || $el.attr('data-value');
            const label = $el.text().trim() || $el.attr('data-label') || '';
            
            if (rating && !isNaN(parseFloat(rating))) {
                ratings.extraction_method = 'data_attributes';
                ratings.data_completeness = 'partial';
                
                // Try to categorize the rating
                if (label.includes('مطور') || label.includes('developer')) {
                    ratings.developer_rating.overall = parseFloat(rating);
                } else if (label.includes('مشروع') || label.includes('project')) {
                    ratings.project_rating.overall = parseFloat(rating);
                }
            }
        });
    }
    
    // Strategy 3: Look for hidden elements that might contain data
    const hiddenElements = $('[style*="display: none"], [style*="visibility: hidden"], .hidden');
    hiddenElements.each((i, el) => {
        const text = $(el).text();
        const ratingMatches = text.match(/(\d+\.?\d*)\s*\/\s*10/g);
        
        if (ratingMatches && ratingMatches.length > 0) {
            console.log(`   🔓 Found ratings in hidden elements`);
            ratings.extraction_method = 'hidden_elements';
            ratings.data_completeness = 'partial';
            
            // Extract first rating as developer rating
            const firstMatch = ratingMatches[0].match(/(\d+\.?\d*)/);
            if (firstMatch) {
                ratings.developer_rating.overall = parseFloat(firstMatch[1]);
            }
            
            // Extract second rating as project rating
            if (ratingMatches.length > 1) {
                const secondMatch = ratingMatches[1].match(/(\d+\.?\d*)/);
                if (secondMatch) {
                    ratings.project_rating.overall = parseFloat(secondMatch[1]);
                }
            }
        }
    });
    
    // Strategy 4: Try to find API endpoint in page source
    const apiMatches = html.match(/\/api\/[^\s"']+ratings[^\s"']*/gi);
    if (apiMatches && apiMatches.length > 0) {
        console.log(`   🔓 Found potential API endpoint: ${apiMatches[0]}`);
        
        try {
            const apiUrl = apiMatches[0].startsWith('http') ? apiMatches[0] : `${BASE_URL}${apiMatches[0]}`;
            const apiResponse = await safeFetch(apiUrl);
            
            if (apiResponse) {
                try {
                    const apiData = JSON.parse(apiResponse);
                    if (apiData.ratings || apiData.data) {
                        console.log(`   ✅ Successfully fetched from API`);
                        ratings.extraction_method = 'api_endpoint';
                        ratings.data_completeness = 'full';
                        Object.assign(ratings, apiData.ratings || apiData.data || apiData);
                    }
                } catch (e) {
                    // API didn't return JSON
                }
            }
        } catch (e) {
            // API fetch failed
        }
    }
    
    // Strategy 5: Check meta tags
    const metaTags = $('meta[property*="rating"], meta[name*="rating"]');
    if (metaTags.length > 0) {
        console.log(`   🔓 Found rating meta tags`);
        metaTags.each((i, el) => {
            const content = $(el).attr('content');
            if (content && !isNaN(parseFloat(content))) {
                ratings.extraction_method = 'meta_tags';
                ratings.data_completeness = 'partial';
                ratings.developer_rating.overall = parseFloat(content);
            }
        });
    }
    
    // Strategy 6: Even if locked, try to extract visible summary data
    const bodyText = $('body').text();
    
    // Look for any visible ratings in the format X.X/10
    const visibleRatings = bodyText.match(/(\d+\.?\d*)\s*\/\s*10/g);
    if (visibleRatings && visibleRatings.length > 0 && ratings.extraction_method === 'none') {
        console.log(`   🔓 Found visible ratings despite lock`);
        ratings.extraction_method = 'visible_text';
        ratings.data_completeness = 'partial';
        
        visibleRatings.forEach((match, idx) => {
            const value = parseFloat(match.match(/(\d+\.?\d*)/)[1]);
            if (idx === 0) ratings.developer_rating.overall = value;
            if (idx === 1) ratings.project_rating.overall = value;
        });
    }
    
    return ratings;
}

// Test the bypass on a known locked compound
async function testPaywallBypass() {
    console.log('🔬 Testing Paywall Bypass Strategies\n');
    
    // Test on compound 129 (we know it exists)
    const testId = 129;
    const testUrl = `${BASE_URL}/compounds-ratings/ar/compound/${testId}`;
    
    console.log(`Testing on: ${testUrl}`);
    const html = await safeFetch(testUrl);
    
    if (!html) {
        console.log('❌ Failed to fetch test page');
        return;
    }
    
    console.log(`✅ Fetched page (${html.length} chars)\n`);
    
    // Save HTML for inspection
    fs.writeFileSync('test_compound_page.html', html);
    console.log('💾 Saved HTML to: test_compound_page.html\n');
    
    const ratings = await extractRatingsWithPaywallBypass(html, testId, testUrl);
    
    console.log('\n📊 Extraction Results:');
    console.log(`   Method: ${ratings.extraction_method}`);
    console.log(`   Completeness: ${ratings.data_completeness}`);
    console.log(`   Developer Rating:`, ratings.developer_rating);
    console.log(`   Project Rating:`, ratings.project_rating);
    
    // Save results
    fs.writeFileSync('test_bypass_results.json', JSON.stringify(ratings, null, 2));
    console.log('\n💾 Saved results to: test_bypass_results.json');
}

testPaywallBypass();
