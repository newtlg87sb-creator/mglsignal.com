// Footer specific translations
const footerTranslations = {
    mn: {
        "foot-links-title": "Хурдан холбоос",
        "foot-about-title": "Бидний тухай",
        "foot-social-title": "Сошиал сувгууд",
        "foot-about": "Танилцуулга",
        "foot-contact": "Холбоо барих",
        "foot-tagline": "Дэлхийн зах зээлийн хөдөлгөөнийг <br> дата шинжилгээгээр түрүүлж мэдэр.",
        "privacy-page-title": "Нууцлалын бодлого",
        "terms-page-title": "Үйлчилгээний нөхцөл",
        "risk-page-title": "Эрсдэлийн анхааруулга",
        "nav-home": "Нүүр", "nav-forex": "Форекс", "nav-crypto": "Крипто", "nav-news": "Мэдээ" // Added for quick links
    },
    en: {
        "foot-links-title": "Fast Links",
        "foot-about-title": "About Us",
        "foot-social-title": "Social Links",
        "foot-about": "About",
        "foot-contact": "Contact",
        "foot-tagline": "Experience global market movements <br> with data intelligence.",
        "privacy-page-title": "Privacy Policy",
        "terms-page-title": "Terms of Service",
        "risk-page-title": "Risk Warning",
        "nav-home": "Home", "nav-forex": "Forex", "nav-crypto": "Crypto", "nav-news": "News" // Added for quick links
    }
};

// Initialize window.translations if it doesn't exist yet
if (typeof window.translations === 'undefined') window.translations = { mn: {}, en: {} };

// Merge footer translations into the global object
Object.keys(footerTranslations).forEach(lang => {
    window.translations[lang] = { 
        ...footerTranslations[lang], 
        ...window.translations[lang] 
    };
});

const footerHTML = `
<footer class="bg-brand-dark-blue border-t border-brand-border pt-8 pb-1">
    <div class="max-w-7xl mx-auto px-6">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 mb-8">
            
            <div>
                <h3 data-i18n="foot-links-title" class="text-brand-gold text-xs font-black uppercase tracking-[0.2em] mb-6">Хурдан холбоос</h3>
                <ul class="space-y-4 text-sm text-gray-400 font-medium">
                    <li><a href="/index.html" data-i18n="nav-home" class="hover:text-white transition">Нүүр</a></li>
                    <li><a href="#" data-i18n="nav-forex" class="hover:text-white transition">Forex</a></li>
                    <li><a href="#" data-i18n="nav-crypto" class="hover:text-white transition">Crypto</a></li>
                    <li><a href="/main_news.html" data-i18n="nav-news" class="hover:text-white transition">Мэдээ</a></li>
                </ul>
            </div>

            <div>
                <h3 data-i18n="foot-about-title" class="text-brand-gold text-xs font-black uppercase tracking-[0.2em] mb-6">Бидний тухай</h3>
                <ul class="space-y-4 text-sm text-gray-400 font-medium">
                    <li><a href="/main_about.html" data-i18n="foot-about" class="hover:text-white transition">Танилцуулга</a></li>
                    <li><a href="/main_contact.html" data-i18n="foot-contact" class="hover:text-white transition">Холбоо барих</a></li>
                </ul>
            </div>

            <div>
                <h3 data-i18n="foot-social-title" class="text-brand-gold text-xs font-black uppercase tracking-[0.2em] mb-6">Сошиал сувгууд</h3>
                <div class="flex space-x-5 text-gray-400">
                    <a href="https://https://www.facebook.com/share/1Dg7fcoaMu/" target="_blank" class="hover:text-brand-gold transition text-xl"><i class="fab fa-facebook-f"></i></a>
                    <a href="https://t.me/Crypto_sharing_world" target="_blank" class="hover:text-brand-gold transition text-xl"><i class="fab fa-telegram-plane"></i></a>
                    <a href="https://www.youtube.com/@mglsignal" target="_blank" class="hover:text-brand-gold transition text-xl"><i class="fab fa-youtube"></i></a>
                </div>
            </div>

            <div class="flex flex-col items-start md:items-end">
                <span class="text-2xl font-black tracking-tighter text-white mb-4 italic">MGL<span class="text-brand-gold font-normal">Signal</span></span>
                <p data-i18n="foot-tagline" class="text-gray-500 text-xs leading-relaxed md:text-right">
                    Дэлхийн зах зээлийн хөдөлгөөнийг <br> дата шинжилгээгээр түрүүлж мэдэр.
                </p>
            </div>
        </div>

    </div>
</footer>

<footer class="bg-brand-dark-blue border-t border-brand-border py-2 mt-auto">
    <div class="max-w-7xl mx-auto px-6">
        <div class="flex flex-col md:flex-row justify-between items-center gap-2">
            <p class="text-[10px] text-gray-500 font-medium tracking-wider uppercase">
                &copy; 2025 MGLSIGNAL.COM. ALL RIGHTS RESERVED.
            </p>
            
            <div class="flex space-x-6 text-[9px] text-gray-600 font-bold uppercase tracking-widest">
                <a href="main_privacy.html" data-i18n="privacy-page-title" class="hover:text-brand-gold transition">Privacy Policy</a>
                <a href="main_terms.html" data-i18n="terms-page-title" class="hover:text-brand-gold transition">Terms of Service</a>
                <a href="main_risk.html" data-i18n="risk-page-title" class="hover:text-brand-gold transition">Risk Warning</a>
            </div>
        </div>
    </div>
</footer>
`;

// This will insert the HTML right before the <script> tag for footer.js
if (document.currentScript) {
    document.currentScript.insertAdjacentHTML('beforebegin', footerHTML);
}