# Développement

Python 3.12+ pour les tests isolés, Node.js et Playwright pour la carte. Le runtime de l'intégration est celui de votre Home Assistant ; les tests isolés ne remplacent pas une installation complète.

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py'
npm install --ignore-scripts
npm test
npx playwright install chromium
npm run test:browser
python tools/check_public_sources.py
python tools/sync_frontend.py --check
python tools/build_release.py
python tools/check_release.py
```

Inventaire VMware et MQTT simulés. Les tests navigateur vérifient mise en page, éditeur et rattachements avec graphiques HA simulés ; ils ne testent pas Recorder ou une installation HA réelle. Captures dans dist/, exclu du dépôt.

Modifier la carte dans `www/infra-vcenter/infrastructure-card.js`, puis lancer `python tools/sync_frontend.py` pour mettre à jour la copie livrée avec l'intégration.

Pour préparer une release, aligner la version dans le manifeste, `const.py` et `package.json`. Lancer les contrôles et joindre les quatre ZIP listés dans `dist/SHA256SUMS` à la release GitHub, avec ce fichier de sommes. Le tag porte le même numéro que le manifeste. `infra_vcenter.zip` contient les fichiers de l'intégration directement à la racine et fournit la carte. Les autres ZIP servent à l'installation manuelle.

La liste distribuable vient de tools/public_sources.py. Le contrôle public recherche adresses privées, chemins personnels et texte mal encodé. Compléter par une revue humaine.

- custom_components/infra_vcenter : VMware et configuration HA.
- www/infra-vcenter/infrastructure-card.js : carte et éditeur sans build frontend.
- collector : Linux/SSH/IPMI et MQTT Discovery.
- tests : données fictives.
- docs et dashboards : installation et exemples.

Conserver les identifiants lors des évolutions. La fusion des sources reste une décision d'affichage. Ne pas fabriquer une puissance système depuis les watts CPU ou des alimentations.

La configuration utilise un listener et async_update_and_abort selon [l'évolution HA](https://contributors.home-assistant.io/blog/2026/05/07/config-entry-listener-together-with-reloading-methods/). L'identité directe repose sur [HostHardwareSummary.uuid](https://developer.broadcom.com/xapis/virtual-infrastructure-json-api/latest/data-structures/HostHardwareSummary/).
