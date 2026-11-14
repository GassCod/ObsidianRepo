const { Plugin, Notice } = require('obsidian');
const { execFile } = require('child_process');
const path = require('path');

class SchoolOrganizerPlugin extends Plugin {
    async onload() {
        console.log('School Organizer plugin loaded');

        // 1. Register command
        this.addCommand({
            id: 'organize',
            name: 'Организовать уроки и обновить оглавление',
            callback: () => this.runOrganizer()
        });

        // 2. Register ribbon icon
        this.addRibbonIcon('folder-sync', 'Организовать уроки и обновить оглавление', () => {
            this.runOrganizer();
        });

        // 3. Automatically integrate with Commander (cmdr) and Excalidraw on layout ready
        this.app.workspace.onLayoutReady(() => {
            this.setupCommanderIntegration();
            this.setupExcalidrawDefaults();
        });
    }

    async setupCommanderIntegration() {
        try {
            const cmdr = this.app.plugins.plugins['cmdr'];
            if (cmdr && cmdr.settings && Array.isArray(cmdr.settings.pageHeader)) {
                const commandId = 'school-organizer:organize';
                const exists = cmdr.settings.pageHeader.some(item => item.id === commandId);
                if (!exists) {
                    cmdr.settings.pageHeader.push({
                        id: commandId,
                        icon: 'lucide-folder-sync',
                        name: 'Организовать уроки и обновить оглавление',
                        mode: 'any'
                    });
                    await cmdr.saveSettings();
                    if (cmdr.manager && cmdr.manager.pageHeader && typeof cmdr.manager.pageHeader.reorder === 'function') {
                        cmdr.manager.pageHeader.reorder();
                    }
                }
            }
        } catch (err) {
            console.error('School Organizer: failed to integrate with Commander:', err);
        }
    }

    async setupExcalidrawDefaults() {
        try {
            const excal = this.app.plugins.plugins['obsidian-excalidraw-plugin'];
            if (!excal) return;

            // 1. Ensure template file path and zoomToFitOnOpen settings
            if (excal.settings) {
                let changed = false;
                if (excal.settings.templateFilePath !== 'Templates/Template.excalidraw.md') {
                    excal.settings.templateFilePath = 'Templates/Template.excalidraw.md';
                    changed = true;
                }
                if (excal.settings.zoomToFitOnOpen !== false) {
                    excal.settings.zoomToFitOnOpen = false;
                    changed = true;
                }
                if (changed && typeof excal.saveSettings === 'function') {
                    await excal.saveSettings();
                }
            }

            // 2. Hook onFileCreateHook for newly created drawings
            if (excal.ea) {
                const oldHook = excal.ea.onFileCreateHook;
                excal.ea.onFileCreateHook = async (data) => {
                    if (oldHook) {
                        try { await oldHook(data); } catch(e) { console.error(e); }
                    }
                    const view = data?.view;
                    if (view) {
                        this.applyExcalidrawPencilAndZoom(view);
                    }
                };
            }

            // 3. Listen on active-leaf-change for empty/new drawings
            this.registerEvent(
                this.app.workspace.on('active-leaf-change', (leaf) => {
                    if (!leaf || !leaf.view || leaf.view.getViewType() !== 'excalidraw') return;
                    const view = leaf.view;
                    setTimeout(() => {
                        try {
                            if (!view || !view.excalidrawAPI) return;
                            const elements = view.excalidrawAPI.getSceneElements?.() || [];
                            const nonDeleted = elements.filter(el => !el.isDeleted);
                            if (nonDeleted.length === 0) {
                                this.applyExcalidrawPencilAndZoom(view);
                            }
                        } catch (err) {
                            console.error('School Organizer: error on leaf change check:', err);
                        }
                    }, 150);
                })
            );
        } catch (err) {
            console.error('School Organizer: failed to setup Excalidraw defaults:', err);
        }
    }

    applyExcalidrawPencilAndZoom(view) {
        if (!view) return;
        const doApply = () => {
            try {
                if (view.semaphores) {
                    view.semaphores.preventAutozoom = true;
                }
                const updates = {
                    activeTool: {
                        type: 'freedraw',
                        customType: null,
                        locked: false,
                        fromSelection: false,
                        lastActiveTool: null
                    },
                    currentItemStrokeColor: '#1e1e1e',
                    currentItemBackgroundColor: 'transparent',
                    currentItemFillStyle: 'solid',
                    currentItemStickynoteStrokeColor: '#1e1e1e',
                    currentItemStrokeWidthKey: 'extraThin',
                    currentItemStrokeVariability: 'variable',
                    currentItemStrokeStyle: 'solid',
                    currentItemRoughness: 1,
                    currentItemOpacity: 100,
                    currentStrokeOptions: {
                        variability: 'variable',
                        streamline: 0.5
                    },
                    zoom: {
                        value: 1.5
                    }
                };

                if (view.excalidrawAPI && typeof view.excalidrawAPI.updateScene === 'function') {
                    view.excalidrawAPI.updateScene({ appState: updates });
                } else if (typeof view.updateScene === 'function') {
                    view.updateScene({ appState: updates });
                }
            } catch (err) {
                console.error('School Organizer: error applying Excalidraw settings:', err);
            }
        };

        doApply();
        setTimeout(doApply, 80);
        setTimeout(doApply, 250);
        setTimeout(doApply, 500);
        setTimeout(() => {
            if (view && view.semaphores) {
                view.semaphores.preventAutozoom = false;
            }
        }, 1200);
    }

    runOrganizer() {
        new Notice('⏳ Организация уроков и обновление оглавления...');

        const basePath = (this.app.vault.adapter && this.app.vault.adapter.basePath) 
            ? this.app.vault.adapter.basePath 
            : '/home/petr/Documents/1/home';
        const scriptPath = path.join(basePath, 'organize_school.py');

        execFile('python3', [scriptPath, basePath], (error, stdout, stderr) => {
            if (error) {
                console.error('School Organizer error:', error, stderr);
                new Notice('❌ Ошибка при организации уроков: ' + (stderr || error.message), 7000);
                return;
            }

            console.log('School Organizer output:\n', stdout);

            let moved = 0;
            const match = stdout.match(/Total moved:\s*(\d+)/);
            if (match) {
                moved = parseInt(match[1], 10);
            }

            if (moved > 0) {
                new Notice(`✅ Оглавления обновлены! Перемещено файлов в папки: ${moved}`, 5000);
            } else {
                new Notice('✅ Все уроки уже рассортированы. Оглавления актуализированы!', 5000);
            }
        });
    }

    onunload() {
        console.log('School Organizer plugin unloaded');
    }
}

module.exports = SchoolOrganizerPlugin;
