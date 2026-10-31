Ce qui revient maintenant à l'agent (cadrage, section « Initialisation ») :

1. **Les questions de départ** : les relire, en ajouter si l'entrée en
   appelle (un trou ou une contradiction du document), sans dépasser le
   plafond, puis les donner à l'humain dans la conversation, avec leur lien.
   Sa réponse se consigne avec son texte exact (`socle answer … --relayed`).
2. **Un document de cadrage** : en tirer les objectifs, les contraintes et
   les décisions, sans le réécrire. Chaque fait tiré du document est
   « supposé », avec le document pour source
   (`source : fichier:memory/archives/<document>#<section>`) ; chaque
   objectif devient un sujet du backlog, avec la même origine.
3. **Un dépôt existant** : les faits mesurés par l'audit sont posés ;
   ajouter seulement ce qu'une commande ou un fichier prouve, le reste est
   « supposé » ou devient une question.
4. **Les deux ensemble** : le dépôt fait foi pour ce qui existe (code,
   tests, outils, CI), le document pour ce qui est voulu ; toute divergence
   devient une question, jamais une correction silencieuse.
5. **Rien** : la mémoire reste vide ; les contrôles sont déjà actifs, le
   reste se découvre en travaillant.

Aucun fait sans source, sauf « supposé » : `socle verify` le vérifie.
