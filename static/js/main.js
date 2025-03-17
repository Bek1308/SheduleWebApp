document.addEventListener('DOMContentLoaded', () => {
    const navLinks = document.querySelectorAll('.nav-link');
    const dropdownLinks = document.querySelectorAll('.dropdown-item[data-page]');
    const settingsLinks = document.querySelectorAll('.settings-link');
    const pageContent = document.getElementById('page-content');
    const sidebar = document.getElementById('sidebar');
    const toggleSidebar = document.getElementById('toggleSidebar');
    const langItems = document.querySelectorAll('.dropdown-item[data-lang]');
    const clock = document.getElementById('clock');
    const themeSwitch = document.getElementById('themeSwitch');
    const cache = new Map();
    let languages = {};
    let customThemes = JSON.parse(localStorage.getItem('customThemes')) || [];
    const username = document.querySelector('.profile-username').textContent.trim();

    if (!pageContent) return console.error("'page-content' topilmadi!");

    // Sidebar toggle
    toggleSidebar.addEventListener('click', () => sidebar.classList.toggle('active'));

    // Dinamik sahifa yuklash
    const loadPage = (page, element) => {
        if (cache.has(page)) {
            pageContent.innerHTML = cache.get(page);
            updateActiveLink(element);
            applySettingsToPage();
            updateLanguage(localStorage.getItem('language') || 'tg');
            bindSettingsEvents();
            return;
        }
        pageContent.innerHTML = '<div class="loading">Yuklanmoqda...</div>';
        fetch(`/pages/${page}`)
            .then(response => {
                if (!response.ok) throw new Error(`Status: ${response.status}`);
                return response.text();
            })
            .then(data => {
                pageContent.innerHTML = data;
                cache.set(page, data);
                updateActiveLink(element);
                applySettingsToPage();
                updateLanguage(localStorage.getItem('language') || 'tg');
                bindSettingsEvents();
            })
            .catch(error => {
                pageContent.innerHTML = `<h1>Xato</h1><p>Sahifa topilmadi! (${error.message})</p>`;
            });
    };

    const updateActiveLink = (element) => {
        navLinks.forEach(link => link.classList.remove('active'));
        if (element) element.classList.add('active');
    };

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            if (page === 'settings') {
                loadSettingsButtons();
            } else {
                loadPage(page, link);
            }
        });
    });

    dropdownLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.getAttribute('data-page');
            loadPage(page, link);
        });
    });

    // Sozlamalar tugmalari (katta tugmalar sifatida)
    const loadSettingsButtons = () => {
        pageContent.innerHTML = `
            <div class="settings-buttons d-flex flex-column gap-3 align-items-center">
                <button class="btn settings-btn btn-lg w-75" data-settings="theme" data-lang-key="predefined_themes"><i class="fas fa-paint-brush"></i> Temalar</button>
                <button class="btn settings-btn btn-lg w-75" data-settings="font" data-lang-key="font_family"><i class="fas fa-font"></i> Shrift</button>
                <button class="btn settings-btn btn-lg w-75" data-settings="clock" data-lang-key="clock_settings"><i class="fas fa-clock"></i> Soat va Sana</button>
                <button class="btn settings-btn btn-lg w-75" data-settings="custom-themes" data-lang-key="custom_themes"><i class="fas fa-palette"></i> Shaxsiy Temalar</button>
            </div>
            <div id="settings-content" class="mt-4"></div>
        `;
        updateLanguage(localStorage.getItem('language') || 'tg');
        document.querySelectorAll('.settings-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const section = btn.getAttribute('data-settings');
                loadSpecificSettings(section);
            });
        });
        updateActiveLink(document.querySelector('.nav-link[data-page="settings"]'));
    };

    // Har bir sozlama uchun alohida qism
    const loadSpecificSettings = (type) => {
        let content = '';
        switch (type) {
            case 'theme':
                content = `
                    <div class="settings-section active">
                        <button class="btn btn-secondary mb-3" id="backToSettings"><i class="fas fa-arrow-left"></i> Orqaga</button>
                        <h3 data-lang-key="predefined_themes"><i class="fas fa-paint-brush"></i> Tayyor Temalar</h3>
                        <div class="d-flex gap-2 flex-wrap">
                            <button class="btn theme-option" data-theme="dark" data-lang-key="dark">Qorong‘i</button>
                            <button class="btn theme-option" data-theme="light" data-lang-key="light">Yorqin</button>
                            <button class="btn theme-option" data-theme="blue" data-lang-key="blue">Ko‘k</button>
                            <button class="btn theme-option" data-theme="purple" data-lang-key="purple">Binafsha</button>
                        </div>
                        <h3 data-lang-key="custom_theme"><i class="fas fa-user-cog"></i> Shaxsiy Tema</h3>
                        <div class="settings-option"><label class="form-label" data-lang-key="theme_name"><i class="fas fa-tag"></i> Tema Nomi</label><input type="text" class="form-control custom-input" id="themeName" placeholder="Tema nomini kiriting"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="background_color">Fon rangi</label><input type="color" class="form-control custom-input" id="backgroundColor" value="#000000"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="text_color">Matn rangi</label><input type="color" class="form-control custom-input" id="textColor" value="#ffffff"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="sidebar_color">Sidebar rangi</label><input type="color" class="form-control custom-input" id="sidebarColor" value="#000000"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="accent_color">Aksent rangi</label><input type="color" class="form-control custom-input" id="accentColor" value="#00cc7a"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="button_color">Tugma rangi</label><input type="color" class="form-control custom-input" id="buttonColor" value="#00cc7a"></div>
                        <div class="settings-option"><label class="form-label" data-lang-key="button_text_color">Tugma matn rangi</label><input type="color" class="form-control custom-input" id="buttonTextColor" value="#ffffff"></div>
                        <button type="button" class="btn mt-2" id="applyCustomTheme" data-lang-key="apply">Qo‘llash</button>
                        <button type="button" class="btn mt-2" id="saveCustomTheme" data-lang-key="save_theme">Saqlash</button>
                    </div>
                `;
                break;
            case 'font':
                content = `
                    <div class="settings-section active">
                        <button class="btn btn-secondary mb-3" id="backToSettings"><i class="fas fa-arrow-left"></i> Orqaga</button>
                        <h3 data-lang-key="font_family"><i class="fas fa-font"></i> Shrift turi</h3>
                        <select class="form-select custom-input" id="fontSelect">
                            <option value="Poppins">Poppins</option>
                            <option value="Arial">Arial</option>
                            <option value="Roboto">Roboto</option>
                            <option value="Times New Roman">Times New Roman</option>
                            <option value="Open Sans">Open Sans</option>
                            <option value="Lato">Lato</option>
                            <option value="Montserrat">Montserrat</option>
                            <option value="Raleway">Raleway</option>
                            <option value="Georgia">Georgia</option>
                        </select>
                    </div>
                `;
                break;
            case 'clock':
                content = `
                    <div class="settings-section active">
                        <button class="btn btn-secondary mb-3" id="backToSettings"><i class="fas fa-arrow-left"></i> Orqaga</button>
                        <h3 data-lang-key="clock_settings"><i class="fas fa-clock"></i> Soat va Sana</h3>
                        <div class="settings-option">
                            <label class="form-label" data-lang-key="timezone">Vaqt zonasi</label>
                            <select class="form-select custom-input" id="timezoneSelect">
                                <option value="Asia/Dushanbe">Dushanbe</option>
                                <option value="Asia/Tashkent">Toshkent</option>
                                <option value="Europe/Moscow">Moskva</option>
                                <option value="America/New_York">Nyu-York</option>
                                <option value="Asia/Tokyo">Tokio</option>
                            </select>
                        </div>
                    </div>
                `;
                break;
            case 'custom-themes':
                content = `
                    <div class="settings-section active">
                        <button class="btn btn-secondary mb-3" id="backToSettings"><i class="fas fa-arrow-left"></i> Orqaga</button>
                        <h3 data-lang-key="custom_themes"><i class="fas fa-palette"></i> Saqlangan Shaxsiy Temalar</h3>
                        <div id="custom-themes-list" class="d-flex gap-2 flex-wrap"></div>
                    </div>
                `;
                break;
        }
        pageContent.innerHTML = content;
        updateLanguage(localStorage.getItem('language') || 'tg');
        bindSettingsEvents();
        if (type === 'custom-themes') loadCustomThemes();

        // Orqaga tugmasi
        document.getElementById('backToSettings').addEventListener('click', loadSettingsButtons);
    };

    settingsLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const settingsType = link.getAttribute('data-settings');
            loadSpecificSettings(settingsType);
        });
    });

    // Saqlangan sozlamalarni qo‘llash
    const applySettingsToPage = () => {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        applyTheme(savedTheme);
        if (savedTheme === 'custom') {
            const customSettings = JSON.parse(localStorage.getItem('customSettings')) || {};
            document.body.style.background = customSettings.bgColor;
            document.body.style.color = customSettings.textColor;
            document.querySelector('.sidebar').style.background = customSettings.sidebarColor;
            document.documentElement.style.setProperty('--accent-color', customSettings.accentColor);
            document.documentElement.style.setProperty('--button-color', customSettings.buttonColor);
            document.documentElement.style.setProperty('--button-text-color', customSettings.buttonTextColor);
        }
        const savedFont = localStorage.getItem('font') || 'Poppins';
        applyFont(savedFont);
        updateClock();
    };

    // Tema qo‘llash
    const applyTheme = (theme) => {
        document.documentElement.classList.remove('dark-theme', 'light-theme', 'blue-theme', 'purple-theme', 'custom-theme');
        document.documentElement.classList.add(`${theme}-theme`);
        if (themeSwitch) themeSwitch.checked = theme === 'dark';
        localStorage.setItem('theme', theme);
        document.body.style.background = '';
        document.body.style.color = '';
        document.querySelector('.sidebar').style.background = '';
        document.documentElement.style.removeProperty('--accent-color');
        document.documentElement.style.removeProperty('--button-color');
        document.documentElement.style.removeProperty('--button-text-color');
    };

    // Shrift qo‘llash (ikonkalarga ta’sir qilmaslik)
    const applyFont = (font) => {
        document.documentElement.style.setProperty('--font-family', font);
        document.querySelectorAll('body, .sidebar, .nav-link, .dropdown-item, .settings-btn, .theme-option, .form-label, h3, .nav-text, .profile-username, .content-body, .clock, .footer-content span').forEach(el => {
            el.style.fontFamily = font;
        });
        localStorage.setItem('font', font);
    };

    // Soat yangilash (barqaror hajm bilan)
    const updateClock = () => {
        const timezone = localStorage.getItem('timezone') || 'Asia/Dushanbe';
        const options = { timeZone: timezone, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
        const time = new Date().toLocaleString('en-US', options);
        clock.style.fontFamily = 'monospace'; // Barqaror hajm uchun monospace shrift
        clock.style.fontSize = '1.5rem';
        clock.textContent = time;
    };
    setInterval(updateClock, 1000);
    updateClock();

    // Shaxsiy temalarni yuklash
    const loadCustomThemes = () => {
        const themesList = document.getElementById('custom-themes-list');
        themesList.innerHTML = '';
        customThemes.forEach((theme, index) => {
            const themeBtn = document.createElement('button');
            themeBtn.className = 'btn theme-option';
            themeBtn.textContent = theme.name;
            themeBtn.addEventListener('click', () => applyCustomTheme(theme));
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-danger ms-2';
            deleteBtn.textContent = 'O‘chirish';
            deleteBtn.addEventListener('click', () => deleteCustomTheme(index));
            const wrapper = document.createElement('div');
            wrapper.appendChild(themeBtn);
            wrapper.appendChild(deleteBtn);
            themesList.appendChild(wrapper);
        });
    };

    const applyCustomTheme = (theme) => {
        document.documentElement.classList.remove('dark-theme', 'light-theme', 'blue-theme', 'purple-theme', 'custom-theme');
        document.documentElement.classList.add('custom-theme');
        document.body.style.background = theme.bgColor;
        document.body.style.color = theme.textColor;
        document.querySelector('.sidebar').style.background = theme.sidebarColor;
        document.documentElement.style.setProperty('--accent-color', theme.accentColor);
        document.documentElement.style.setProperty('--button-color', theme.buttonColor);
        document.documentElement.style.setProperty('--button-text-color', theme.buttonTextColor);
        localStorage.setItem('theme', 'custom');
        localStorage.setItem('customSettings', JSON.stringify(theme));
    };

    const deleteCustomTheme = (index) => {
        customThemes.splice(index, 1);
        localStorage.setItem('customThemes', JSON.stringify(customThemes));
        loadCustomThemes();
    };

    // Sozlamalar hodisalari
    const bindSettingsEvents = () => {
        const themeOptions = document.querySelectorAll('.theme-option');
        const applyCustomThemeBtn = document.getElementById('applyCustomTheme');
        const saveCustomThemeBtn = document.getElementById('saveCustomTheme');
        const fontSelect = document.getElementById('fontSelect');
        const timezoneSelect = document.getElementById('timezoneSelect');

        themeOptions.forEach(option => {
            option.addEventListener('click', () => {
                const theme = option.getAttribute('data-theme');
                applyTheme(theme);
            });
        });

        if (applyCustomThemeBtn) {
            applyCustomThemeBtn.addEventListener('click', () => {
                const theme = {
                    name: document.getElementById('themeName').value || 'Custom Theme',
                    bgColor: document.getElementById('backgroundColor').value,
                    textColor: document.getElementById('textColor').value,
                    sidebarColor: document.getElementById('sidebarColor').value,
                    accentColor: document.getElementById('accentColor').value,
                    buttonColor: document.getElementById('buttonColor').value,
                    buttonTextColor: document.getElementById('buttonTextColor').value
                };
                applyCustomTheme(theme);
            });
        }

        if (saveCustomThemeBtn) {
            saveCustomThemeBtn.addEventListener('click', () => {
                const theme = {
                    name: document.getElementById('themeName').value || `Custom Theme ${customThemes.length + 1}`,
                    bgColor: document.getElementById('backgroundColor').value,
                    textColor: document.getElementById('textColor').value,
                    sidebarColor: document.getElementById('sidebarColor').value,
                    accentColor: document.getElementById('accentColor').value,
                    buttonColor: document.getElementById('buttonColor').value,
                    buttonTextColor: document.getElementById('buttonTextColor').value
                };
                customThemes.push(theme);
                localStorage.setItem('customThemes', JSON.stringify(customThemes));
                alert('Tema saqlandi!');
            });
        }

        if (fontSelect) {
            fontSelect.addEventListener('change', () => {
                const font = fontSelect.value;
                applyFont(font);
            });
            fontSelect.value = localStorage.getItem('font') || 'Poppins';
        }

        if (timezoneSelect) {
            timezoneSelect.addEventListener('change', () => {
                const timezone = timezoneSelect.value;
                localStorage.setItem('timezone', timezone);
                updateClock();
            });
            timezoneSelect.value = localStorage.getItem('timezone') || 'Asia/Dushanbe';
        }

        if (themeSwitch) {
            themeSwitch.addEventListener('change', () => {
                const theme = themeSwitch.checked ? 'dark' : 'light';
                applyTheme(theme);
            });
        }
    };

    // Til boshqaruvi
    const updateLanguage = (lang) => {
        document.querySelectorAll('[data-lang-key]').forEach(el => {
            const key = el.getAttribute('data-lang-key');
            if (languages[lang] && languages[lang][key]) {
                const icon = el.querySelector('i');
                const textSpan = el.querySelector('.nav-text') || el;
                if (icon && textSpan.classList.contains('nav-text')) {
                    textSpan.textContent = languages[lang][key];
                } else if (!icon || textSpan === el) {
                    el.textContent = languages[lang][key];
                }
            }
        });
        localStorage.setItem('language', lang);
    };

    langItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const lang = item.getAttribute('data-lang');
            updateLanguage(lang);
            if (document.querySelector('.settings-buttons')) {
                loadSettingsButtons();
            }
        });
    });

    fetch('/static/languages.json')
        .then(response => {
            if (!response.ok) throw new Error('languages.json yuklanmadi');
            return response.json();
        })
        .then(data => {
            languages = data;
            const savedLang = localStorage.getItem('language') || 'tg';
            updateLanguage(savedLang);
            loadPage('home', document.querySelector('.nav-link[data-page="home"]'));
        })
        .catch(error => console.error('Til faylini yuklashda xato:', error));

    // Boshlang‘ich sozlamalar
    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme);
    if (savedTheme === 'custom') {
        const customSettings = JSON.parse(localStorage.getItem('customSettings')) || {};
        document.body.style.background = customSettings.bgColor;
        document.body.style.color = customSettings.textColor;
        document.querySelector('.sidebar').style.background = customSettings.sidebarColor;
        document.documentElement.style.setProperty('--accent-color', customSettings.accentColor);
        document.documentElement.style.setProperty('--button-color', customSettings.buttonColor);
        document.documentElement.style.setProperty('--button-text-color', customSettings.buttonTextColor);
    }
    const savedFont = localStorage.getItem('font') || 'Poppins';
    applyFont(savedFont);
});