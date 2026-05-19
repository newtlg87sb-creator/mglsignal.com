/**
 * Access Control Script - MGL Signal
 * Шалгаж буй хуудсанд нэвтрэх эрх байгаа эсэхийг хянана.
 */
(function() {
    const userStr = localStorage.getItem('user');
    const currentPage = window.location.pathname;

    // Хэрэв хэрэглэгч огт нэвтрээгүй бол
    if (!userStr || userStr === "undefined") {
        window.location.href = 'main_login.html';
        return;
    }

    const user = JSON.parse(userStr);

    // Alpha хуудсанд орох гэж байвал эрхийг нь шалгах
    if (currentPage.includes('main_alpha_signals.html')) {
        const now = new Date();
        const expiresAt = user.membership_expires_at ? new Date(user.membership_expires_at) : null;
        const isExpired = expiresAt && expiresAt < now;

        if (user.membership_type !== 'alpha' || isExpired) {
            const msg = isExpired ? 'Таны ALPHA эрхийн хугацаа дууссан байна.' : 'Энэ хуудсанд нэвтрэхийн тулд ALPHA багцтай байх шаардлагатай.';
            alert(msg);
            window.location.href = 'main_pricing.html';
        }
    }
})();