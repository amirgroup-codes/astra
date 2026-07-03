# Prebiotic Synthesis of L-Proline: Comprehensive Literature Review

## 1. Known Prebiotic Synthesis Routes

One experimentally demonstrated pathway produces L-Proline (C5H9NO2, SMILES: C1CC(NC1)C(=O)O, InChI: InChI=1S/C5H9NO2/c7-5(8)4-2-1-3-6-4/h4,6H,1-3H2,(H,7,8), MW: 115.13) from prebiotically available precursors via cyanosulfidic chemistry in surface environments.

### Pathway 1: Cyanosulfidic Pyrrolidine Route (Surface Environment)

This 5-step pathway builds the pyrrolidine ring of proline through a sequence of cyanohydrin formation, thiolation-cyclization, reductive deoxygenation, thione-to-nitrile exchange, and nitrile hydrolysis. The entire chemistry was demonstrated by Patel, Percivalle, Ritson, Duffy, and Sutherland (2015, *Nature Chemistry*, DOI: 10.1038/nchem.2202) as part of the cyanosulfidic protometabolism framework.

**Step 1 — Cyanohydrin formation**: 3-aminopropanal + HCN → 4-amino-2-hydroxybutanenitrile
- SMILES: NCCC=O.C#N>>N#CC(O)CCN
- Environment: Surface (evaporitic pools, cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature and pressure
- Mechanism: Strecker-type cyanohydrin formation — hydrogen cyanide (CHN, SMILES: C#N, InChI: InChI=1S/CHN/c1-2/h1H, MW: 27.03) undergoes nucleophilic addition to the aldehyde carbonyl of 3-aminopropanal (C3H7NO, SMILES: C(CN)C=O, InChI: InChI=1S/C3H7NO/c4-2-1-3-5/h3H,1-2,4H2, MW: 73.09). The cyanide ion attacks the electrophilic carbonyl carbon, forming a new C–C bond and yielding the α-hydroxynitrile (cyanohydrin) 4-amino-2-hydroxybutanenitrile (C4H8N2O, SMILES: C(CN)C(C#N)O, InChI: InChI=1S/C4H8N2O/c5-2-1-4(7)3-6/h4,7H,1-2,5H2, MW: 100.12). The free amine group on the 3-aminopropanal is preserved for subsequent cyclization.

**Step 2 — Thiolation and cyclization**: 4-amino-2-hydroxybutanenitrile + H₂S → 3-hydroxypyrrolidine-2-thione + NH₃
- SMILES: N#CC(O)CCN.S>>OC1CCNC1=S.N
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature, H₂S atmosphere
- Mechanism: Hydrogen sulfide (H2S, SMILES: S, InChI: InChI=1S/H2S/h1H2, MW: 34.08) attacks the nitrile carbon of 4-amino-2-hydroxybutanenitrile, converting the C≡N group to a thioamide (C=S). The primary amine at the opposite end of the chain then undergoes intramolecular cyclization by attacking the thioamide carbon, forming the five-membered pyrrolidine ring. This produces 3-hydroxypyrrolidine-2-thione (C4H7NOS, SMILES: C1CNC(=S)C1O, InChI: InChI=1S/C4H7NOS/c6-3-1-2-5-4(3)7/h3,6H,1-2H2,(H,5,7), MW: 117.17) with release of ammonia (NH3, SMILES: N, InChI: InChI=1S/H3N/h1H3, MW: 17.03). This step simultaneously achieves ring closure and introduces the thione functional group that is central to the subsequent cyanosulfidic transformations.

**Step 3 — Reductive deoxygenation**: 3-hydroxypyrrolidine-2-thione → pyrrolidine-2-thione + H₂O
- SMILES: OC1CCNC1=S>>S=C1CCCN1.O
- Environment: Surface (cyanosulfidic conditions)
- Agents: **Sulfidic acid** (H₂S, SMILES: S) and **Elemental copper** ([Cu], SMILES: [Cu])
- Conditions: Aqueous, ambient temperature
- Mechanism: Reductive deoxygenation — the hydroxyl group at C3 of 3-hydroxypyrrolidine-2-thione is removed with loss of water (H2O, SMILES: O, InChI: InChI=1S/H2O/h1H2, MW: 18.01). Elemental copper acts as a reductant in concert with hydrogen sulfide. The Cu/H₂S system provides the reducing equivalents needed to cleave the C–OH bond, yielding pyrrolidine-2-thione (C4H7NS, SMILES: C1CC(=S)NC1, InChI: InChI=1S/C4H7NS/c6-4-2-1-3-5-4/h1-3H2,(H,5,6), MW: 101.17). This step is critical for producing the fully reduced pyrrolidine ring needed for the final proline product.

**Step 4 — Thione-to-nitrile exchange**: pyrrolidine-2-thione + HCN → pyrrolidine-2-carbonitrile + H₂S
- SMILES: S=C1CCCN1.C#N>>N#CC1CCCN1.S
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature, HCN present
- Mechanism: The thione (C=S) group of pyrrolidine-2-thione is displaced by cyanide. HCN attacks the thioamide carbon, replacing the sulfur with a nitrile group. This thione-to-nitrile exchange releases H₂S and produces pyrrolidine-2-carbonitrile (C5H8N2, SMILES: C1CC(NC1)C#N, InChI: InChI=1S/C5H8N2/c6-4-5-2-1-3-7-5/h5,7H,1-3H2, MW: 96.13). The released H₂S is recycled back into the cyanosulfidic network. This reaction converts the sulfur-containing heterocycle into a nitrile-bearing pyrrolidine that can undergo hydrolysis to the carboxylic acid (proline).

**Step 5 — Nitrile hydrolysis**: pyrrolidine-2-carbonitrile + 2 H₂O → L-Proline + NH₃
- SMILES: N#CC1CCCN1.O.O>>N.O=C(O)C1CCCN1
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature
- Mechanism: Hydrolysis of the nitrile group (C≡N) of pyrrolidine-2-carbonitrile — water attacks the nitrile carbon nucleophilically, forming a primary amide intermediate (pyrrolidine-2-carboxamide), which undergoes a second hydrolysis to the carboxylic acid with release of ammonia. Two equivalents of water are consumed. The product is L-Proline (C5H9NO2, SMILES: C1CC(NC1)C(=O)O, InChI: InChI=1S/C5H9NO2/c7-5(8)4-2-1-3-6-4/h4,6H,1-3H2,(H,7,8), MW: 115.13), a cyclic (pyrrolidine-containing) amino acid.

This 5-step pathway is notable because it constructs the pyrrolidine ring — a structural feature unique to proline among the proteinogenic amino acids — through cyanosulfidic chemistry. The pathway showcases the role of H₂S and HCN as interconverting sulfur and nitrogen functional groups through thioamide and nitrile intermediates, a hallmark of the Powell-Sutherland cyanosulfidic framework.

## 2. Key Intermediates and Precursors

### Hub Molecule: 4-amino-2-hydroxybutanenitrile (C4H8N2O)
- Formula: C4H8N2O
- SMILES: C(CN)C(C#N)O
- InChI: InChI=1S/C4H8N2O/c5-2-1-4(7)3-6/h4,7H,1-2,5H2
- MW: 100.12
- Role: **Key branch-point intermediate** — this aminonitrile cyanohydrin is the product of the Strecker-type addition of HCN to 3-aminopropanal. It contains both the free amine and nitrile groups required for the subsequent thiolation-cyclization step that forms the pyrrolidine ring. It is consumed by H₂S-mediated cyclization to produce 3-hydroxypyrrolidine-2-thione (Patel et al., 2015).

### Hub Molecule: pyrrolidine-2-thione (C4H7NS)
- Formula: C4H7NS
- SMILES: C1CC(=S)NC1
- InChI: InChI=1S/C4H7NS/c6-4-2-1-3-5-4/h1-3H2,(H,5,6)
- MW: 101.17
- Role: **Central cyclic intermediate** — pyrrolidine-2-thione is the reduced pyrrolidine ring bearing a thione group. It is produced by reductive deoxygenation of 3-hydroxypyrrolidine-2-thione (using Cu/H₂S), and consumed by thione-to-nitrile exchange with HCN to produce pyrrolidine-2-carbonitrile. This molecule sits at the junction between the ring-formation steps and the nitrile/hydrolysis steps that produce proline (Patel et al., 2015).

### Hub Molecule: hydrogen cyanide (CHN)
- Formula: CHN
- SMILES: C#N
- InChI: InChI=1S/CHN/c1-2/h1H
- MW: 27.03
- Role: **Upstream hub — carbon and nitrogen source** — HCN participates in two distinct reactions in the network: (1) Strecker-type cyanohydrin formation with 3-aminopropanal (Step 1), and (2) thione-to-nitrile exchange with pyrrolidine-2-thione (Step 4). HCN is a prebiotically abundant molecule produced by atmospheric photochemistry (UV irradiation of N₂/CH₄/CO₂ mixtures), volcanic outgassing, and impact-generated synthesis.

### Hub Molecule: hydrogen sulfide (H₂S)
- Formula: H2S
- SMILES: S
- InChI: InChI=1S/H2S/h1H2
- MW: 34.08
- Role: **Recycled sulfur carrier** — H₂S is consumed in Step 2 (thiolation-cyclization) and regenerated in Step 4 (thione-to-nitrile exchange), creating a catalytic sulfur cycle. It also serves as a co-reductant with elemental copper in Step 3 (reductive deoxygenation). H₂S is prebiotically abundant from volcanic outgassing and hydrothermal vents.

### Other Key Molecules

**3-aminopropanal** (C3H7NO)
- Formula: C3H7NO
- SMILES: C(CN)C=O
- InChI: InChI=1S/C3H7NO/c4-2-1-3-5/h3H,1-2,4H2
- MW: 73.09
- Role: Starting material — the C3 amino aldehyde that provides the carbon backbone and amine nitrogen for the pyrrolidine ring. 3-aminopropanal can form prebiotically from acrolein (propenal) + NH₃, or from Michael addition of ammonia to acrolein. It is produced in cyanosulfidic reaction networks from simple C1–C3 feedstocks (Patel et al., 2015).

**3-hydroxypyrrolidine-2-thione** (C4H7NOS)
- Formula: C4H7NOS
- SMILES: C1CNC(=S)C1O
- InChI: InChI=1S/C4H7NOS/c6-3-1-2-5-4(3)7/h3,6H,1-2H2,(H,5,7)
- MW: 117.17
- Role: First cyclic intermediate — formed by H₂S-mediated thiolation and intramolecular cyclization of 4-amino-2-hydroxybutanenitrile. Retains a hydroxyl group at C3 that is removed in the subsequent reductive deoxygenation step. This intermediate demonstrates the simultaneous ring closure and thione formation that is characteristic of cyanosulfidic pyrrolidine synthesis (Patel et al., 2015).

**pyrrolidine-2-carbonitrile** (C5H8N2)
- Formula: C5H8N2
- SMILES: C1CC(NC1)C#N
- InChI: InChI=1S/C5H8N2/c6-4-5-2-1-3-7-5/h5,7H,1-3H2
- MW: 96.13
- Role: Penultimate intermediate — the nitrile-bearing pyrrolidine produced by thione-to-nitrile exchange. Both the pyrrolidine ring and the C5 carbon skeleton are complete at this stage; only hydrolysis of the nitrile to a carboxylic acid remains to yield proline (Patel et al., 2015).

**Ammonia** (NH₃)
- Formula: H3N
- SMILES: N
- InChI: InChI=1S/H3N/h1H3
- MW: 17.03
- Role: Byproduct released in Step 2 (cyclization) and Step 5 (nitrile hydrolysis). Prebiotically abundant from volcanic outgassing, atmospheric photochemistry, and hydrothermal systems. Recycled as nitrogen source for other prebiotic reactions.

### Starting Molecules
- **H₂O**: SMILES: O, InChI: InChI=1S/H2O/h1H2
- **HCN** (hydrogen cyanide): SMILES: C#N, InChI: InChI=1S/CHN/c1-2/h1H
- **H₂S** (hydrogen sulfide): SMILES: S, InChI: InChI=1S/H2S/h1H2
- **NH₃** (ammonia): SMILES: N, InChI: InChI=1S/H3N/h1H3
- **3-aminopropanal**: SMILES: C(CN)C=O, InChI: InChI=1S/C3H7NO/c4-2-1-3-5/h3H,1-2,4H2

## 3. Reaction Mechanisms and Conditions

### Reaction R1: Cyanohydrin formation (Strecker-type)
- 3-aminopropanal + HCN → 4-amino-2-hydroxybutanenitrile
- SMILES: NCCC=O.C#N>>N#CC(O)CCN
- Environment: Surface (evaporitic pools, cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature and pressure
- Source: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015), *Nature Chemistry*, DOI: 10.1038/nchem.2202
- Mechanism: Nucleophilic addition of cyanide to the aldehyde carbonyl of 3-aminopropanal, forming the cyanohydrin (α-hydroxynitrile) 4-amino-2-hydroxybutanenitrile. This is the carbon–carbon bond forming step that extends the C3 aldehyde to the C4 aminonitrile, setting up the chain length needed for pyrrolidine ring formation.

### Reaction R2: Thiolation-cyclization
- 4-amino-2-hydroxybutanenitrile + H₂S → 3-hydroxypyrrolidine-2-thione + NH₃
- SMILES: N#CC(O)CCN.S>>OC1CCNC1=S.N
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature, H₂S atmosphere
- Source: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015), *Nature Chemistry*, DOI: 10.1038/nchem.2202
- Mechanism: H₂S attacks the nitrile carbon, converting C≡N to a thioamide (C=S). The terminal amine then performs intramolecular nucleophilic attack on the thioamide carbon, closing the five-membered pyrrolidine ring and releasing NH₃. This one-pot thiolation-cyclization is characteristic of cyanosulfidic chemistry, where H₂S activates nitriles toward cyclization.

### Reaction R3: Reductive deoxygenation
- 3-hydroxypyrrolidine-2-thione → pyrrolidine-2-thione + H₂O
- SMILES: OC1CCNC1=S>>S=C1CCCN1.O
- Environment: Surface (cyanosulfidic conditions)
- Agents: **Sulfidic acid** (H₂S, SMILES: S) and **Elemental copper** ([Cu], SMILES: [Cu])
- Conditions: Aqueous, ambient temperature
- Source: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015), *Nature Chemistry*, DOI: 10.1038/nchem.2202
- Mechanism: Reductive removal of the C3 hydroxyl group. The Cu/H₂S reducing system donates electrons to cleave the C–OH bond, producing the fully reduced pyrrolidine-2-thione with loss of water. Elemental copper is a plausible prebiotic reductant in cyanosulfidic scenarios — copper deposits are formed by reduction of dissolved Cu²⁺ by H₂S in surface geochemical settings.

### Reaction R4: Thione-to-nitrile exchange
- pyrrolidine-2-thione + HCN → pyrrolidine-2-carbonitrile + H₂S
- SMILES: S=C1CCCN1.C#N>>N#CC1CCCN1.S
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature, HCN present
- Source: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015), *Nature Chemistry*, DOI: 10.1038/nchem.2202
- Mechanism: Cyanide displaces the thione sulfur at C2 of the pyrrolidine ring. HCN acts as a nucleophile, attacking the electrophilic thioamide carbon. The C=S bond is broken with release of H₂S, and a new C–CN bond is formed, yielding the nitrile. This reaction converts a sulfur-containing functional group to a nitrogen-containing one — a key interconversion in cyanosulfidic chemistry. The released H₂S is recycled for use in Step 2 (thiolation-cyclization).

### Reaction R5: Nitrile hydrolysis
- pyrrolidine-2-carbonitrile + 2 H₂O → L-Proline + NH₃
- SMILES: N#CC1CCCN1.O.O>>N.O=C(O)C1CCCN1
- Environment: Surface (cyanosulfidic conditions)
- Conditions: Aqueous, ambient temperature
- Source: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015), *Nature Chemistry*, DOI: 10.1038/nchem.2202
- Mechanism: Sequential hydrolysis of the nitrile group — water attacks the nitrile carbon, forming a primary amide intermediate (pyrrolidine-2-carboxamide), which undergoes further hydrolysis to the carboxylic acid with release of ammonia. Two equivalents of water are consumed. This completes the conversion of the nitrile to the carboxylate, yielding L-Proline.

## 4. Mineral Catalysts and Surfaces

The following agents are experimentally documented for reactions in the L-Proline synthesis network:

- **Elemental copper (Cu⁰)**: Metallic copper (SMILES: [Cu]). Acts as a reductant in the Cu/H₂S system for the reductive deoxygenation of 3-hydroxypyrrolidine-2-thione to pyrrolidine-2-thione (Reaction R3). Elemental copper is prebiotically plausible — native copper deposits form when dissolved Cu²⁺ ions are reduced by H₂S in geochemical settings. Copper is found in hydrothermal and surface environments associated with sulfide mineralization. Used in: reductive deoxygenation (Patel et al., 2015).

- **Hydrogen sulfide (H₂S)**: Sulfidic acid (SMILES: S). Dual role: (1) acts as a co-reductant with elemental copper in the reductive deoxygenation step (Reaction R3), and (2) serves as the sulfur source for thiolation-cyclization (Reaction R2) and is regenerated by thione-to-nitrile exchange (Reaction R4). H₂S is abundantly available from volcanic outgassing, hydrothermal vents, and sulfide mineral dissolution. Used in: thiolation-cyclization (Reaction R2) and reductive deoxygenation (Reaction R3).

## 5. Experimental Evidence

### Study 1: Patel, Percivalle, Ritson, Duffy, and Sutherland (2015)
- **Title**: "Common origins of RNA, protein and lipid precursors in a cyanosulfidic protometabolism"
- **Journal**: Nature Chemistry
- **DOI**: 10.1038/nchem.2202
- **Key finding**: Demonstrated a unified cyanosulfidic chemistry starting from HCN, H₂S, and simple aldehydes that produces precursors to RNA, proteins, and lipids under plausible prebiotic surface conditions. For proline specifically, this study established the complete 5-step pathway from 3-aminopropanal + HCN through a series of cyanosulfidic transformations: (1) cyanohydrin formation → 4-amino-2-hydroxybutanenitrile, (2) H₂S-mediated thiolation and intramolecular cyclization → 3-hydroxypyrrolidine-2-thione, (3) Cu/H₂S reductive deoxygenation → pyrrolidine-2-thione, (4) HCN-driven thione-to-nitrile exchange → pyrrolidine-2-carbonitrile, and (5) nitrile hydrolysis → L-Proline. The pathway is notable for constructing the pyrrolidine ring — unique among proteinogenic amino acids — through cyanosulfidic ring closure rather than through conventional Strecker synthesis, which cannot form cyclic amino acids. The Cu/H₂S reducing system used in Step 3 demonstrates that prebiotically available metals and sulfur species can drive reductive transformations needed for amino acid synthesis. The recycling of H₂S (consumed in Step 2, regenerated in Step 4) exemplifies the catalytic sulfur cycling central to the cyanosulfidic framework.

## 6. Environmental Context

### Surface Environment (Primary)
All five reactions in the L-Proline synthesis pathway operate under surface cyanosulfidic conditions:
- **Evaporitic pools and geothermal surface settings**: The reactions occur at ambient temperature and pressure in aqueous solution, consistent with shallow surface pools near volcanic/geothermal sources where HCN and H₂S are delivered by outgassing.
- **Cyanosulfidic conditions**: The pathway requires co-availability of HCN and H₂S — conditions found at the interface of volcanic degassing zones and surface water bodies. UV irradiation (relevant for other cyanosulfidic transformations) may also play a role in generating or activating some of the feedstocks.
- **Copper availability**: Elemental copper for the reductive deoxygenation step (Reaction R3) is prebiotically plausible in surface settings where dissolved Cu²⁺ ions from weathered copper minerals are reduced by H₂S to deposit native copper.
- **3-Aminopropanal production**: The starting material 3-aminopropanal is itself a product of cyanosulfidic/surface chemistry — it can form from acrolein (produced by formaldehyde condensation or thermal decomposition of glycerol) reacting with ammonia, or from reductive amination of malondialdehyde.

### Environmental Interconnection
- **Surface → Biochemical**: L-Proline produced by this pathway enters the prebiotic amino acid pool. As a cyclic imino acid with a rigid pyrrolidine ring, proline introduces structural constraints (kinks and turns) into prebiotic peptides. Proline-containing peptides formed by wet-dry cycling on clay surfaces in the Biochemical environment would have distinct conformational properties compared to peptides composed only of linear amino acids.
- **Hydrothermal → Surface**: Simple feedstock molecules (HCN, H₂S, NH₃, aldehydes) can be produced in hydrothermal environments and transported to surface pools via ocean circulation and volcanic outgassing, where they fuel the cyanosulfidic proline synthesis pathway.

## 7. Open Questions and Challenges

1. **3-Aminopropanal availability**: The pathway begins with 3-aminopropanal, a reactive amino aldehyde whose prebiotic concentration and stability in surface pools is uncertain. As an aldehyde, it is susceptible to oxidation, polymerization, and reaction with other nucleophiles present in the prebiotic milieu. The flux of 3-aminopropanal production versus its consumption by competing reactions is a key constraint on this pathway.

2. **Chirality**: The cyanosulfidic pathway produces racemic proline (equal L and D). The origin of homochirality (biological preference for L-proline) is unresolved. Possible enantioselection mechanisms include asymmetric crystallization, chiral mineral surfaces, or amplification through autocatalytic cycles, but none has been definitively demonstrated for proline.

3. **Copper availability and oxidation state**: The reductive deoxygenation step (Reaction R3) requires elemental copper (Cu⁰). While native copper can form from Cu²⁺ reduction by H₂S, the steady-state concentration of Cu⁰ in prebiotic surface environments is poorly constrained. Whether sufficient Cu⁰ would persist in the presence of other oxidants and complexing agents is an open question.

4. **Cyclic vs. linear amino acid selectivity**: The cyanosulfidic pathway is specific to cyclic amino acids (proline) because the cyclization step (Reaction R2) depends on the intramolecular distance between the amine and the thioamide. For 3-aminopropanal, this distance is exactly right for five-membered ring formation. Whether similar pathways could produce other ring sizes (e.g., pipecolic acid from 4-aminobutanal) is an interesting extension.

5. **H₂S recycling efficiency**: The pathway features an elegant sulfur cycle where H₂S is consumed in Step 2 and regenerated in Step 4. However, the efficiency of this recycling under real prebiotic conditions — with H₂S loss to oxidation, mineral precipitation (as metal sulfides), and atmospheric escape — may limit the catalytic turnover.

6. **Nitrile hydrolysis rate**: The final step (Reaction R5) requires hydrolysis of pyrrolidine-2-carbonitrile to the carboxylic acid. Nitrile hydrolysis at ambient temperature and neutral pH can be slow (days to weeks). The kinetics of this step under realistic prebiotic conditions (variable pH, temperature fluctuations, presence of metal ions that could catalyze hydrolysis) need further characterization.

7. **Yield and selectivity**: While Patel et al. (2015) demonstrated all the individual steps, the overall yield of proline through the complete 5-step sequence has not been reported for a one-pot continuous process. Side reactions at each step (particularly the competing intermolecular reactions of the aminonitrile intermediate) could reduce the net yield significantly.
