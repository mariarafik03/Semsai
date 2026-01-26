
import { chromium } from 'playwright';
import fs from 'fs';
import { parse } from 'csv-parse/sync';
import { stringify } from 'csv-stringify/sync';
import path from 'path';

const INPUT_CSV = 'c:/Users/Mohamed Hany/Desktop/Semsai-1/SemsAi/nawy (1).csv';
const OUTPUT_CSV = 'c:/Users/Mohamed Hany/Desktop/Semsai-1/SemsAi/nawy_enriched.csv';
const PROGRESS_FILE = 'c:/Users/Mohamed Hany/Desktop/Semsai-1/semsai-backend/enrichment_progress.json';

// Batch size for parallel requests
const BATCH_SIZE = 5;
const LIMIT = null; // Production run

async function enrich() {
    console.log('Starting Enrichment Scraper...');

    const fileContent = fs.readFileSync(INPUT_CSV, 'utf-8');
    const records = parse(fileContent, {
        columns: true,
        skip_empty_lines: true
    });

    console.log(`Loaded ${records.length} records.`);
    const processedRecords = LIMIT ? records.slice(0, LIMIT) : records;
    if (LIMIT) console.log(`Limiting to ${LIMIT} records for testing.`);

    let startIndex = 0;
    let enrichedData = [];

    if (fs.existsSync(PROGRESS_FILE)) {
        const progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf-8'));
        startIndex = progress.index;
        enrichedData = progress.data || [];
        console.log(`Resuming from index ${startIndex}`);
    }

    const browser = await chromium.launch({ headless: true });

    for (let i = startIndex; i < processedRecords.length; i += BATCH_SIZE) {
        const batch = processedRecords.slice(i, i + BATCH_SIZE);
        console.log(`Processing batch ${i} to ${Math.min(i + BATCH_SIZE, processedRecords.length)}...`);

        const promises = batch.map(async (record) => {
            const url = record['tablescraper-selected-row href'];
            if (!url || !url.startsWith('http')) return record;

            const context = await browser.newContext();
            const page = await context.newPage();

            try {
                // Navigate and block unnecessary resources
                await page.route('**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}', route => route.abort());
                await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

                // Extract __NEXT_DATA__
                const data = await page.evaluate(() => {
                    const nextData = document.getElementById('__NEXT_DATA__');
                    if (!nextData) return null;
                    const json = JSON.parse(nextData.textContent);
                    const prop = json.props.pageProps.property;
                    return {
                        deliveryDate: prop.deliveryDate,
                        finishing: prop.finishing,
                        amenities: (prop.amenities || []).map(a => a.name || a.label || a),
                        lat: prop.latitude || (prop.compound ? prop.compound.latitude : null),
                        lng: prop.longitude || (prop.compound ? prop.compound.longitude : null),
                        isGated: prop.compound ? (prop.compound.description?.toLowerCase().includes('gated community') || prop.compound.metaDescription?.toLowerCase().includes('gated community')) : false,
                        unitCount: prop.compound ? prop.compound.propertiesCount : null
                    };
                });

                if (data) {
                    record['delivery_extracted'] = data.deliveryDate ? new Date(data.deliveryDate).getFullYear() : 'Unknown';
                    record['finishing_extracted'] = data.finishing || 'Unknown';
                    record['amenities_extracted'] = data.amenities.join(' | ');
                    record['lat_extracted'] = data.lat;
                    record['lng_extracted'] = data.lng;
                    record['is_gated_extracted'] = data.isGated ? 'Yes' : 'No';
                    record['unit_count_extracted'] = data.unitCount || '';
                }

            } catch (err) {
                console.error(`Error scraping ${url}: ${err.message}`);
            } finally {
                try {
                    if (context) await context.close();
                } catch (e) { }
            }

            return record;
        });

        const results = await Promise.all(promises);
        enrichedData.push(...results);

        // Save progress every batch
        fs.writeFileSync(PROGRESS_FILE, JSON.stringify({ index: i + BATCH_SIZE, data: enrichedData }));

        // Write periodic CSV update
        const csvOutput = stringify(enrichedData, { header: true });
        fs.writeFileSync(OUTPUT_CSV, csvOutput);
    }

    await browser.close();
    console.log('Enrichment Complete! Saved to ' + OUTPUT_CSV);
    fs.unlinkSync(PROGRESS_FILE); // Cleanup
}

enrich().catch(err => {
    console.error('Fatal Error:', err);
    process.exit(1);
});
