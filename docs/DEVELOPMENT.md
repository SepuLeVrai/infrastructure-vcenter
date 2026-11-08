# DÃ©veloppement

Python 3.12+ pour les tests isolÃ©s, Node.js et Playwright pour la carte. Le runtime de l'intÃ©gration est celui de votre Home Assistant ; les tests isolÃ©s ne remplacent pas une installation complÃ¨te.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
npm install --ignore-scripts
npm test
npx playwright install chromium
npm run test:browser
python tools/check_public_sources.py
python tools/build_release.py
```

Inventaire VMware et MQTT simulÃ©s. Les tests navigateur vÃ©rifient mise en page, Ã©diteur et rattachements avec graphiques HA simulÃ©s ; ils ne testent pas Recorder ou une installation HA rÃ©elle. Captures dans dist/, exclu du dÃ©pÃ´t.

Archives complÃ¨te, interface seule et collecteur dans dist/. La liste distribuable vient de tools/public_sources.py. Les secrets, configurations d'exploitation et anciennes archives sont exclus. Le contrÃ´le public recherche adresses privÃ©es et chemins personnels ; complÃ©ter par une revue humaine.

- custom_components/infra_vcenter : VMware et configuration HA.
- www/infra-vcenter/infrastructure-card.js : carte et Ã©diteur sans build frontend.
- collector : Linux/SSH/IPMI et MQTT Discovery.
- tests : donnÃ©es fictives.
- docs et dashboards : installation et exemples.

Conserver les identifiants lors des Ã©volutions. La fusion des sources reste une dÃ©cision d'affichage. Ne pas fabriquer une puissance systÃ¨me depuis les watts CPU ou des alimentations.

La configuration utilise un listener et async_update_and_abort selon [l'Ã©volution HA](https://contributors.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/). L'identitÃ© directe repose sur [HostHardwareSummary.uuid](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/data-structures/HostHardwareSummary/).
