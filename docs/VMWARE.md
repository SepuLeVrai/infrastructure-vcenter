# Configuration VMware

Adresses IP ou DNS sans https://, port ni chemin. Le port a son propre champ. Les listes ESXi sont sÃ©parÃ©es par `;` et dÃ©dupliquÃ©es.

## Avec vCenter

Renseigner vCenter, le compte en lecture seule, son mot de passe et le port HTTPS (443 par dÃ©faut). Laisser ESXi vide pour tout collecter.

Pour limiter le pÃ©rimÃ¨tre : `192.0.2.11;esxi02.example.invalid`. Comparaison au nom inventoriÃ©, DNS configurÃ© et IP VMkernel. Cette liste filtre vCenter ; elle n'ajoute pas de connexion directe. Une sÃ©lection absente ou invisible avec le compte est refusÃ©e.

Les totaux concernent le pÃ©rimÃ¨tre sÃ©lectionnÃ©. Chaque datastore partagÃ© y est comptÃ© une seule fois.

## Sans vCenter

Laisser vCenter vide et saisir `192.0.2.11;192.0.2.12` dans ESXi. Utiliser un **compte local ESXi**, pas un compte SSO vCenter. Les hÃ´tes d'une entrÃ©e partagent utilisateur, mot de passe, port et choix TLS. CrÃ©er plusieurs entrÃ©es si nÃ©cessaire.

Les identifiants VMware sont prÃ©fixÃ©s par l'UUID matÃ©riel de l'hÃ´te. Les alias IP/DNS d'un mÃªme ESXi ne doublent pas ses donnÃ©es. Un hÃ´te inaccessible rend ses entitÃ©s connues indisponibles, tandis que les autres continuent. Si tous sont injoignables, l'entrÃ©e est indisponible.

Un datastore partagÃ© peut apparaÃ®tre sur plusieurs hÃ´tes directs : aucun total global de capacitÃ© n'est calculÃ© sans identitÃ© commune fiable. Ã‰viter de configurer simultanÃ©ment les mÃªmes hÃ´tes via vCenter et directement : ces modes ont des identitÃ©s distinctes et ne fusionnent pas automatiquement leurs VM.

## Certificats et modifications

Conserver la vÃ©rification TLS avec un certificat valide reconnu par Home Assistant. Un certificat autosignÃ© ou Ã©mis pour un nom alors que vous utilisez l'IP peut Ã©chouer. DÃ©sactiver temporairement la vÃ©rification aide au diagnostic : HTTPS reste utilisÃ© mais le serveur n'est plus authentifiÃ© par certificat. Corriger DNS/certificat selon votre environnement.

Home Assistant doit joindre les endpoints sur le port HTTPS choisi. Les droits et outils invitÃ©s dÃ©terminent les donnÃ©es rÃ©ellement disponibles.

Le menu **Reconfigurer** de l'entrÃ©e modifie les adresses/liste et redemande les identifiants. Un autre vCenter ou un changement de mode nÃ©cessite une entrÃ©e sÃ©parÃ©e. **Configurer** rÃ¨gle l'intervalle de 30 Ã  3600 secondes (60 par dÃ©faut).

Un retrait du pÃ©rimÃ¨tre arrÃªte les mises Ã  jour ; les anciennes entitÃ©s du registre ne sont pas supprimÃ©es automatiquement. Les contrÃ´ler puis supprimer celles devenues inutiles aprÃ¨s sauvegarde des historiques souhaitÃ©s.
