# Configuration VMware

Adresses IP ou DNS sans https://, port ni chemin. Le port a son propre champ. Les listes ESXi sont séparées par `;` et dédupliquées.

## Avec vCenter

Renseigner vCenter, le compte en lecture seule, son mot de passe et le port HTTPS (443 par défaut). Laisser ESXi vide pour tout collecter.

Pour limiter le périmètre : `192.0.2.11;esxi02.example.invalid`. Comparaison au nom inventorié, DNS configuré et IP VMkernel. Cette liste filtre vCenter ; elle n'ajoute pas de connexion directe. Une sélection absente ou invisible avec le compte est refusée.

Les totaux concernent le périmètre sélectionné. Chaque datastore partagé y est compté une seule fois.

## Sans vCenter

Laisser vCenter vide et saisir `192.0.2.11;192.0.2.12` dans ESXi. Utiliser un **compte local ESXi**, pas un compte SSO vCenter. Les hôtes d'une entrée partagent utilisateur, mot de passe, port et choix TLS. Créer plusieurs entrées si nécessaire.

Les identifiants VMware sont préfixés par l'UUID matériel de l'hôte. Les alias IP/DNS d'un même ESXi ne doublent pas ses données. Un hôte inaccessible rend ses entités connues indisponibles, tandis que les autres continuent. Si tous sont injoignables, l'entrée est indisponible.

Un datastore partagé peut apparaître sur plusieurs hôtes directs : aucun total global de capacité n'est calculé sans identité commune fiable. Éviter de configurer simultanément les mêmes hôtes via vCenter et directement : ces modes ont des identités distinctes et ne fusionnent pas automatiquement leurs VM.

## Certificats et modifications

Conserver la vérification TLS avec un certificat valide reconnu par Home Assistant. Un certificat autosigné ou émis pour un nom alors que vous utilisez l'IP peut échouer. Désactiver temporairement la vérification aide au diagnostic : HTTPS reste utilisé mais le serveur n'est plus authentifié par certificat. Corriger DNS/certificat selon votre environnement.

Home Assistant doit joindre les endpoints sur le port HTTPS choisi. Les droits et outils invités déterminent les données réellement disponibles.

Le menu **Reconfigurer** de l'entrée modifie les adresses/liste et redemande les identifiants. Un autre vCenter ou un changement de mode nécessite une entrée séparée. **Configurer** règle l'intervalle de 30 à 3600 secondes (60 par défaut).

Un retrait du périmètre arrête les mises à jour ; les anciennes entités du registre ne sont pas supprimées automatiquement. Les contrôler puis supprimer celles devenues inutiles après sauvegarde des historiques souhaités.
