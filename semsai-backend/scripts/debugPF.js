
import { chromium } from 'playwright';

async function debugPFSearch(query) {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();
    
    console.log(`Searching for: ${query}`);
    try {
        const searchUrl = `https://www.propertyfinder.eg/en/search?c=1&ob=mr&q=${encodeURIComponent(query)}`;
        await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
        
        const data = await page.evaluate(() => {
            const script = document.getElementById('__NEXT_DATA__');
            if (!script) return null;
            return JSON.parse(script.textContent);
        });

        if (!data) {
            console.log('No __NEXT_DATA__ found');
            return;
        }

        const listings = data.props?.pageProps?.searchResult?.listings || [];
        console.log(`Found ${listings.length} listings.`);
        
        if (listings.length > 0) {
            const first = listings[0].property;
            console.log('First listing data:');
            console.log(` - ID: ${first.id}`);
            console.log(` - Location Name: ${first.location?.name}`);
            console.log(` - Location Full Name: ${first.location?.full_name}`);
            console.log(` - Location ID: ${first.location?.id}`);
            console.log(' - Location Tree:');
            first.location_tree?.forEach(t => console.log(`   * ${t.name} (ID: ${t.id}, Level: ${t.level})`));
        }

    } catch (err) {
        console.error('Error:', err.message);
    } finally {
        await browser.close();
    }
}

debugPFSearch('Mountain View 4');
