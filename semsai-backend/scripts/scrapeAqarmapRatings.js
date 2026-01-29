
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Anti-ban configuration
const HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
};

const BASE_URL = 'https://aqarmap.com.eg';
const RATINGS_URL = `${BASE_URL}/compounds-ratings/ar`;

// Randomized delay between requests (3-8 seconds)
function randomDelay() {
    const min = 3000;
    const max = 8000;
    const delay = Math.floor(Math.random() * (max - min + 1)) + min;
    return new Promise(resolve => setTimeout(resolve, delay));
}

// Safe fetch with error handling
async function safeFetch(url, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            console.log(`   Fetching: ${url}`);
            const response = await fetch(url, { headers: HEADERS });
            
            if (response.status === 429) {
                console.log(`   ⚠️ Rate limited (429). Waiting 30 seconds...`);
                await new Promise(resolve => setTimeout(resolve, 30000));
                continue;
            }
            
            if (response.status === 403) {
                console.log(`   ⚠️ Access forbidden (403). Stopping to avoid ban.`);
                return null;
            }
            
            if (response.status !== 200) {
                console.log(`   ⚠️ Status ${response.status}`);
                if (i < retries - 1) {
                    await randomDelay();
                    continue;
                }
                return null;
            }
            
            return await response.text();
        } catch (error) {
            console.error(`   Error: ${error.message}`);
            if (i < retries - 1) {
                await randomDelay();
            }
        }
    }
    return null;
}

// Extract compound data from table rows
function extractCompoundsFromTable(html) {
    const $ = cheerio.load(html);
    const compounds = [];
    
    // Find all rows in the compound table
    $('#compoundTable tr, #compoundTableWraper tbody tr').each((i, row) => {
        const $row = $(row);
        const cells = $row.find('td');
        
        if (cells.length < 4) return; // Skip invalid rows
        
        // Extract compound ID (hidden in first td)
        const compoundId = parseInt($(cells[0]).text().trim());
        if (!compoundId || isNaN(compoundId)) return;
        
        // Extract compound name and developer
        const nameCell = $(cells[1]);
        const compoundName = nameCell.find('span').first().text().trim() || nameCell.text().trim();
        const developerName = nameCell.find('span[style*="color"]').text().trim();
        
        // Extract customer complaints count
        const complaintsCount = parseInt($(cells[2]).text().trim()) || 0;
        
        // Extract experts count
        const expertsCount = parseInt($(cells[3]).text().trim()) || 0;
        
        // Extract status (الحالة)
        const statusCell = $(cells[4]);
        const statusText = statusCell.text().trim();
        const status = statusText.includes('مغلق') ? 'closed' : 'open';
        
        // Build compound URL
        const compoundUrl = `${BASE_URL}/compounds-ratings/ar/compound/${compoundId}`;
        
        compounds.push({
            compound_id: compoundId,
            compound_name: compoundName,
            developer_name: developerName,
            customer_complaints: complaintsCount,
            experts_count: expertsCount,
            status: status,
            compound_url: compoundUrl
        });
    });
    
    return compounds;
}

// Extract detailed ratings from compound page with paywall bypass
function extractDetailedRatings(html, compoundId) {
    const $ = cheerio.load(html);
    
    const ratings = {
        compound_id: compoundId,
        developer_rating: {},
        project_rating: {},
        extraction_method: 'standard',
        data_completeness: 'partial'
    };
    
    const bodyText = $('body').text();
    
    // PAYWALL BYPASS STRATEGY: Extract visible ratings even from "locked" pages
    // Many locked pages still show the overall ratings in the HTML
    const visibleRatings = bodyText.match(/(\d+\.?\d*)\s*\/\s*10/g);
    if (visibleRatings && visibleRatings.length >= 2) {
        // First rating is usually developer rating
        const devMatch = visibleRatings[0].match(/(\d+\.?\d*)/);
        if (devMatch) {
            ratings.developer_rating.overall = parseFloat(devMatch[1]);
            ratings.extraction_method = 'visible_text_bypass';
        }
        
        // Second rating is usually project rating
        const projMatch = visibleRatings[1].match(/(\d+\.?\d*)/);
        if (projMatch) {
            ratings.project_rating.overall = parseFloat(projMatch[1]);
        }
        
        // If we found ratings, mark as partial success even if locked
        if (ratings.developer_rating.overall || ratings.project_rating.overall) {
            ratings.data_completeness = 'partial';
            ratings.status = bodyText.includes('مغلق') ? 'closed_bypassed' : 'open';
        }
    }
    
    // Try to extract detailed metrics (works better on open pages)
    const devRatingSection = $('*:contains("تقييم المطور")').closest('div, section');
    if (devRatingSection.length > 0) {
        const devRatingText = devRatingSection.text();
        
        // Extract individual metrics
        const experienceMatch = devRatingText.match(/الخبرة[^\d]*(\d+\.?\d*)/);
        const reputationMatch = devRatingText.match(/السمعة[^\d]*(\d+\.?\d*)/);
        const deliveryMatch = devRatingText.match(/الالتزام[^\d]*(\d+\.?\d*)|التسليم[^\d]*(\d+\.?\d*)/);
        
        if (experienceMatch) ratings.developer_rating.experience = parseFloat(experienceMatch[1]);
        if (reputationMatch) ratings.developer_rating.reputation = parseFloat(reputationMatch[1]);
        if (deliveryMatch) ratings.developer_rating.delivery_commitment = parseFloat(deliveryMatch[1] || deliveryMatch[2]);
        
        if (experienceMatch || reputationMatch || deliveryMatch) {
            ratings.extraction_method = 'full_extraction';
            ratings.data_completeness = 'full';
        }
    }
    
    // Find project rating section
    const projRatingSection = $('*:contains("تقييم المشروع")').closest('div, section');
    if (projRatingSection.length > 0) {
        const projRatingText = projRatingSection.text();
        
        // Extract individual metrics
        const locationMatch = projRatingText.match(/الموقع[^\d]*(\d+\.?\d*)/);
        const servicesMatch = projRatingText.match(/الخدمات[^\d]*(\d+\.?\d*)/);
        const brokersMatch = projRatingText.match(/الوسطاء[^\d]*(\d+\.?\d*)/);
        
        if (locationMatch) ratings.project_rating.location = parseFloat(locationMatch[1]);
        if (servicesMatch) ratings.project_rating.services = parseFloat(servicesMatch[1]);
        if (brokersMatch) ratings.project_rating.brokers_issues = parseFloat(brokersMatch[1]);
    }
    
    // Final status check
    if (!ratings.status) {
        ratings.status = bodyText.includes('مغلق') ? 'closed' : 'open';
    }
    
    return ratings;
}

// Main scraping function
async function scrapeAllRatings() {
    console.log('🚀 Starting Aqarmap Ratings Scraper');
    console.log('⚠️  Using safe, human-like browsing patterns\n');
    
    const allCompounds = [];
    const detailedRatings = [];
    let currentPage = 1;
    const maxPages = 38; // We know there are 38 pages from pagination
    let consecutiveErrors = 0;
    
    // STEP 1: Scrape all listing pages
    console.log('📋 STEP 1: Scraping compound listings...\n');
    
    while (currentPage <= maxPages && consecutiveErrors < 3) {
        console.log(`📄 Page ${currentPage}/${maxPages}:`);
        
        const url = `${RATINGS_URL}?page=${currentPage}`;
        const html = await safeFetch(url);
        
        if (!html) {
            consecutiveErrors++;
            console.log(`   ❌ Failed to fetch page ${currentPage}`);
            if (consecutiveErrors >= 3) {
                console.log('   ⚠️ Too many errors. Stopping pagination.');
                break;
            }
            await randomDelay();
            continue;
        }
        
        consecutiveErrors = 0;
        const compounds = extractCompoundsFromTable(html);
        
        if (compounds.length === 0) {
            console.log('   ℹ️  No compounds found on this page.');
        } else {
            console.log(`   ✅ Found ${compounds.length} compounds`);
            allCompounds.push(...compounds);
        }
        
        currentPage++;
        await randomDelay();
    }
    
    console.log(`\n✅ Total compounds found: ${allCompounds.length}`);
    console.log(`   Open: ${allCompounds.filter(c => c.status === 'open').length}`);
    console.log(`   Closed: ${allCompounds.filter(c => c.status === 'closed').length}\n`);
    
    // Save intermediate results
    const listingsPath = path.join(__dirname, '../aqarmap_listings.json');
    fs.writeFileSync(listingsPath, JSON.stringify(allCompounds, null, 2));
    console.log(`💾 Saved listings to: ${listingsPath}\n`);
    
    // STEP 2: Scrape detail pages (ALL compounds - including locked ones with bypass)
    console.log('📊 STEP 2: Scraping detailed ratings (ALL compounds with paywall bypass)...\n');
    
    // Process ALL compounds, not just open ones
    const compoundsToProcess = allCompounds;
    let processedCount = 0;
    
    for (const compound of compoundsToProcess) {
        processedCount++;
        const statusIcon = compound.status === 'open' ? '🔓' : '🔒';
        console.log(`[${processedCount}/${compoundsToProcess.length}] ${statusIcon} ${compound.compound_name} (ID: ${compound.compound_id})`);
        
        const html = await safeFetch(compound.compound_url);
        
        if (!html) {
            console.log('   ❌ Failed to fetch details');
            detailedRatings.push({
                ...compound,
                data_completeness: 'failed'
            });
            await randomDelay();
            continue;
        }
        
        const ratings = extractDetailedRatings(html, compound.compound_id);
        
        const fullData = {
            ...compound,
            ...ratings,
            data_source: 'aqarmap',
            scraped_at: new Date().toISOString()
        };
        
        detailedRatings.push(fullData);
        
        console.log(`   ✅ ${ratings.data_completeness} data extracted`);
        
        // Save progress every 10 compounds
        if (processedCount % 10 === 0) {
            const progressPath = path.join(__dirname, '../aqarmap_ratings_progress.json');
            fs.writeFileSync(progressPath, JSON.stringify(detailedRatings, null, 2));
            console.log(`   💾 Progress saved (${processedCount}/${openCompounds.length})`);
        }
        
        await randomDelay();
    }
    
    // STEP 3: Save final results
    console.log('\n💾 Saving final results...');
    
    const finalPath = path.join(__dirname, '../aqarmap_ratings_final.json');
    fs.writeFileSync(finalPath, JSON.stringify(detailedRatings, null, 2));
    
    console.log(`\n✅ SCRAPING COMPLETE!`);
    console.log(`   Total compounds: ${allCompounds.length}`);
    console.log(`   Detailed ratings: ${detailedRatings.length}`);
    console.log(`   Full data: ${detailedRatings.filter(r => r.data_completeness === 'full').length}`);
    console.log(`   Partial data: ${detailedRatings.filter(r => r.data_completeness === 'partial').length}`);
    console.log(`   Locked: ${detailedRatings.filter(r => r.data_completeness === 'locked').length}`);
    console.log(`\n📁 Results saved to: ${finalPath}`);
}

// Run the scraper
scrapeAllRatings().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
