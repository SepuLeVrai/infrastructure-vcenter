# Installation Home Assistant

La version 0.4.1 demande Home Assistant Core 2026.6 ou ultérieur. Sur HAOS, passer par le Marketplace ou HACS selon la version de Home Assistant. Home Assistant installe la dépendance VMware déclarée dans le manifeste.

## Installer depuis le dépôt

1. Dans **Paramètres → Marketplace**, choisir **Ajouter depuis un lien**. Dans HACS, ouvrir **⋮ → Dépôts personnalisés**. Connecter GitHub si l'interface le demande.
2. Ajouter l'URL `https://github.com/SepuLeVrai/infrastructure-vcenter` et sélectionner le type **Intégration** si le choix est proposé.
3. Ouvrir **Infrastructure vCenter**, télécharger la version **0.4.1**, puis redémarrer Home Assistant.
4. Pour une première installation, ouvrir **Paramètres → Appareils et services → Ajouter une intégration**, sélectionner **Infrastructure vCenter**, puis suivre le [paramétrage VMware](VMWARE.md).
5. Créer une vue avec la [carte Infrastructure](../dashboards/INSTALLATION-VUE.md).

[Guide du Marketplace](https://www.home-assistant.io/integrations/marketplace/#custom-repositories) et [guide HACS](https://hacs.dev/docs/faq/custom_repositories/).

## Reprendre une installation manuelle

1. Faire une sauvegarde Home Assistant et garder une copie du YAML de la carte.
2. Télécharger la version 0.4.1 depuis le dépôt personnalisé, dans le dossier existant `custom_components/infra_vcenter`.
3. Conserver l'entrée VMware existante, puis redémarrer Home Assistant et actualiser le navigateur.
4. Vérifier la vue Infrastructure, ses noms, ses rattachements iDRAC et ses mesures de puissance.

L'intégration conserve le domaine `infra_vcenter` et les identifiants des entités existantes. Les identifiants VMware sont enregistrés dans l'entrée Home Assistant. Les rattachements, noms et capteurs de puissance restent dans la configuration de la carte.

Si les ressources du tableau de bord sont gérées dans l'interface, le démarrage de l'intégration crée ou actualise la ressource JavaScript. L'ancienne URL `/local/infra-vcenter/infrastructure-card.js` est reconnue, même avec un paramètre de version. La nouvelle URL est `/infra-vcenter/infrastructure-card.js?v=0.4.1`. Si les ressources sont déclarées en YAML, remplacer l'URL dans l'entrée existante.

En cas de retour à une version antérieure, remettre l'ancienne version de l'intégration et l'URL du JavaScript précédent, puis redémarrer. Garder la copie JavaScript déjà présente sous `/config/www/infra-vcenter` pour ce retour.

## Installer ou mettre à jour par Samba

Télécharger l'archive complète sur la [page de la release](https://github.com/SepuLeVrai/infrastructure-vcenter/releases/tag/0.4.1). Copier le dossier `custom_components/infra_vcenter` vers `/config/custom_components/infra_vcenter` et vérifier que `manifest.json` se trouve directement dans ce dossier. Redémarrer Home Assistant et suivre les étapes de configuration ou de vérification ci-dessus.

Pour Linux/IPMI seuls, l'intégration VMware n'est pas nécessaire : installer le collecteur avec MQTT natif, puis la carte. Le collecteur s'installe sur Debian, pas dans HAOS.

Le collecteur Linux/IPMI se met à jour séparément. Conserver ses fichiers `config.json` et `secrets.env` et suivre le [guide du collecteur](../collector/README.md).

Les comptes VMware doivent avoir un rôle en lecture seule propagé sur l'inventaire concerné. Protéger les sauvegardes Home Assistant contenant leurs identifiants.
