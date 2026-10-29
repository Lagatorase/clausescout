# Error analysis: hybrid-qwen7b-v1 (val, threshold 0.15)

Examples are picked at random (seed fixed) so they are not the most flattering or the worst. Quotes are shortened to 300 characters.

## Cap On Liability

1 missed, 18 false alarms, 2 found with the wrong quote.

- Missed in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: "THE PARTIES ACKNOWLEDGE THAT LIQUIDATED DAMAGES PAYABLE BY YOU UNDER THIS AGREEMENT (WHETHER PRE-OPENING LIQUIDATED DAMAGES OR LIQUIDATED DAMAGES FOR EARLY TERMINATION) ARE NOT PUNITIVE OR EXEMPLARY DAMAGES."
- False alarm in *RareElementResourcesLtd_20171019_SC 13D_EX-99.4_10897534_EX-* (score 0.73): "COMPANY WILL HAVE NO LIABILITY WHATSOEVER TO INVESTOR OR ANY OTHER PERSON FOR OR ON ACCOUNT OF ANY INJURY, LOSS OR DAMAGE OF ANY KIND OR NATURE, SUSTAINED BY, OR ANY DAMAGES ASSESSED OR ASSERTED AGAINST, OR ANY OTHER LIABILITY INCURRED BY OR IMPOSED ON INVESTOR OR ANY OTHER PERSON, ARISING OUT OF OR..."
- False alarm in *BORROWMONEYCOM,INC_06_11_2020-EX-10.1-JOINT VENTURE AGREEMEN* (score 0.64): "The Members will not be personally liable for the return of all or part of the Capital Contributions of a Member, except as otherwise provided in this Agreement."
- False alarm in *ON4COMMUNICATIONSINC_07_02_2009-EX-10.1-PROMOTION AGREEMENT* (score 0.17): "Such a consumer wil l be entitled to visit a custom interactive landing page at the CharityTunes.com website to enter the unique code and consumer's valid email address to receive downloads up to a maximum of either three (3), five (5), or seven (7) free MP3 song downloads having a retail value of $..."
- Wrong quote in *Antares Pharma, Inc. - Manufacturing Agreement*: gave "Provided that (i) AMAG and Antares have agreed to the terms of an Alternate Arrangement, or (ii) AMAG commences purchasing Devices, Components, Products, sample Products and/or Trainers directly from ...", gold starts "The Parties acknowledge and agree that title to and risk of loss of all Prefilled Syringes shall at all times belong to and remain in AMAG; provided that, subject to the limitations on liability set f..."
- Wrong quote in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT *: gave "In the event that the amount of the Termination -4- Payment is determined pursuant to this Section 4.2 to be less than or equal to zero, then no Termination Payment shall be due to HDI nor shall HDI b...", gold starts "In the event the Company terminates this Agreement, the Company shall pay to HDI a termination payment, (the "Termination Payment") the amount of which shall be an amount equal to the aggregate Net Sa..."

## Uncapped Liability

0 missed, 26 false alarms, 3 found with the wrong quote.

- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.91): "This Agreement does not provide, and is not intended to be construed or deemed to provide, any policyholder of the Company with recourse to or against any of the assets of AIG."
- False alarm in *GULFSOUTHMEDICALSUPPLYINC_12_24_1997-EX-4-AFFILIATE AGREEMEN* (score 0.16): "The undersigned further recognizes that, in the event that the undersigned is a director or officer of PSS or becomes a director or officer of PSS upon consummation of the Merger, among other things, any sale of PSS Common Stock by the undersigned within a period of less than six months following th..."
- False alarm in *MARTINMIDSTREAMPARTNERSLP_01_23_2004-EX-10.3-TRANSPORTATION * (score 1.00): "The foregoing indemnities shall expressly exclude any liability for consequential, punitive, special or similar damages, including, without limitation, lost profits."
- Wrong quote in *FuelcellEnergyInc_20191106_8-K_EX-10.1_11868007_EX-10.1_Deve*: gave "In no event will either Party be liable to the other Party under this Agreement for any consequential, indirect, special, incidental, punitive or exemplary loss or damage, including, without limitatio...", gold starts "Notwithstanding anything to the contrary in this Agreement, each Party will bear full responsibility, without limit, for the following: (i) Gross Negligence or Willful Misconduct attributable to its p..."
- Wrong quote in *BLUEFLYINC_03_27_2002-EX-10.27-e-business Hosting Agreement*: gave "Regardless of the basis on which IBM is entitled to claim damages from Customer (including fundamental breach, negligence, misrepresentation, or other contract or tort claim), Customer is liable for n...", gold starts "In no event will either party be liable to the other for special, incidental, or indirect damages or for any consequential damages (including lost profits or savings), even if they are informed of the..."
- Wrong quote in *PareteumCorp_20081001_8-K_EX-99.1_2654808_EX-99.1_Hosting Ag*: gave "In no event shall either Party be liable for indirect or consequential loss or damage, including but not limited to, loss of profit, loss of sales or turnover, loss of or damage to reputation, loss of...", gold starts "Limitation of liability as described in this article shall not apply: a) in case the damage or loss is caused by a Party's willful misconduct (including fraud) or gross negligence, or b) in case of a ..."

## Termination For Convenience

1 missed, 24 false alarms, 0 found with the wrong quote.

- Missed in *ROCKYMOUNTAINCHOCOLATEFACTORY,INC_12_23_2019-EX-10.2-STRATEG*: "If the Farids Group determines for any reason not to proceed with any proposed registration requested pursuant to Section 6.1, the Farids Group shall promptly notify the Company in writing."
- False alarm in *ATHENSBANCSHARESCORP_11_02_2009-EX-1.2-AGENCY AGREEMENT , 20* (score 0.85): "The Agent may terminate this Agreement by giving the notice indicated below in this Section 12 at any time after this Agreement becomes effective as follows:"
- False alarm in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT * (score 0.90): "This Agreement shall be automatically renewed for an additional one year period on each anniversary of the Effective Date, unless terminated by either Party hereto upon ninety (90) days written notice to the other."
- False alarm in *RareElementResourcesLtd_20171019_SC 13D_EX-99.4_10897534_EX-* (score 0.60): "Investor at any time may provide written notice to Company of a material breach of this IP Agreement."

## Change Of Control

0 missed, 31 false alarms, 2 found with the wrong quote.

- False alarm in *RareElementResourcesLtd_20171019_SC 13D_EX-99.4_10897534_EX-* (score 0.78): "Any change of control resulting from any such bankruptcy proceeding shall be subject to the rights and licenses granted in this IP Agreement."
- False alarm in *BLUEFLYINC_03_27_2002-EX-10.27-e-business Hosting Agreement* (score 0.19): "Notwithstanding the foregoing, Customer may assign this Agreement to a successor organization by merger, consolidation or acquisition."
- False alarm in *UAGHINC_04_14_2004-EX-10.18-MAINTENANCE AGREEMENT* (score 0.99): "The Company shall not sell, transfer or otherwise attempt to convey or dispose of any part of the Fiber Ring Assets, other than sales and leases of capacity or of individual fiber strands in the ordinary and usual course of business unless the Provider consents to such transaction, which consent wil..."
- Wrong quote in *CardlyticsInc_20180112_S-1_EX-10.16_11002987_EX-10.16_Mainte*: gave "Bank of America may not unreasonably withhold its consent of assignment in the event the supplier merges or consolidates with another entity.", gold starts "A Termination Event shall have occurred if:"
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "The following Transfers are permitted without giving notice or obtaining our consent if the Permitted Transfer does not result in a change in Control of the Franchisee, the Hotel or the Hotel Site and...", gold starts "We will have sixty (60) days from our receipt of the completed and signed franchise application to consent or withhold our consent to any proposed Change of Ownership Transfer."

## Anti-Assignment

1 missed, 6 false alarms, 1 found with the wrong quote.

- Missed in *2ThemartComInc_19990826_10-12G_EX-10.10_6700288_EX-10.10_Co-*: "All rights (under any applicable intellectual property right) granted herein are not sublicenseable,"
- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.56): "corporate structure or ownership of the Company, or (b) AIG sells the Company to an acquirer, in each case, (i) having a rating from at least one of S&P, Moody's, A.M. Best or a substitute agency, which is a nationally recognized statistical rating organization, that is at least equal to the lower o..."
- False alarm in *ALAMOGORDOFINANCIALCORP_12_16_1999-EX-1-AGENCY AGREEMENT* (score 0.53): "The Company, the MHC and the Bank will not sell or issue, contract to sell or otherwise dispose of, for a period of 90 days after the Closing Date, without the Agent's prior written consent, any Common Stock other than the Shares or other than in connection with any plan or arrangement described in ..."
- False alarm in *ATHENSBANCSHARESCORP_11_02_2009-EX-1.2-AGENCY AGREEMENT , 20* (score 0.82): "The Company and the Bank will not sell or issue, contract to sell or otherwise dispose of, for a period of 90 days after the Closing Date, without the Agent's prior written consent, any of their shares of their common stock, other than the Common Shares or other than in connection with any plan or a..."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "We may assign or Transfer this Agreement or any of our rights, duties, or assets under this Agreement, by operation of law or otherwise, to any person or legal entity without your consent, provided th...", gold starts "We may immediately terminate this Agreement on notice to you and without any opportunity to cure the default if:"

## Exclusivity

0 missed, 22 false alarms, 3 found with the wrong quote.

- False alarm in *PFSFUNDS_06_26_2020-EX-99.H OTH MAT CONT-SERVICES AGREEMENT* (score 0.20): "Nothing in this Agreement shall prevent the Adviser or any affiliated person of the Adviser from providing services for any other person, firm or corporation, including other investment companies; provided, however, that the Adviser expressly represents that it will undertake no activities which, in..."
- False alarm in *ANIXABIOSCIENCESINC_06_09_2020-EX-10.1-COLLABORATION AGREEME* (score 0.81): "During the term of this Agreement, except in the performance of its obligations or exercise of its rights under this Agreement, neither OntoChem nor any of its Affiliates will discover, research, develop, manufacture or commercialize any compound or product directed to any Target, either independent..."
- False alarm in *FuelcellEnergyInc_20191106_8-K_EX-10.1_11868007_EX-10.1_Deve* (score 0.63): "During the Term of this Agreement, FCE will not conduct any Work using Generation 1 Technology in Carbon Capture Applications or any Work using Generation 2 Technology, independently or with third parties outside this Agreement, without prior written approval from ExxonMobil."
- Wrong quote in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT *: gave "Except as provided in Section 6.2, during the term of this Agreement, the Company shall not participate in any project similar to the Site on the Internet with respect to Deerskin Products or products...", gold starts "HDI shall have the exclusive right to use of the "Deerskin" brand for a self-contained web site for the offering of Deerskin Products directly to the consumer on the Internet."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "You will deliver all goods and materials containing the Marks to us and we will have the sole and exclusive use of any items containing the Marks.", gold starts "The only reservation service or system you may use for outgoing reservations referred by or from the Hotel to other Network Hotels will be the Reservation Service or other reservation services we desi..."
- Wrong quote in *AMERICANPHYSICIANSCAPITALINC_03_31_2003-EX-10.26-AGENCY AGRE*: gave "In return for the exclusive appointment of Agency by MICOA to sell its professional liability products listed on the &sbsp;attached Commission Schedule in Nevada, Agency agrees not to sell any competi...", gold starts "In order to allow SC&W to expand the distribution system in Nevada with select and controlled subagents, an exclusive agency agreement will be negotiated which will spell out the terms and conditions ..."

## Non-Compete

0 missed, 21 false alarms, 3 found with the wrong quote.

- False alarm in *PacificapEntertainmentHoldingsInc_20051115_8-KA_EX-1.01_4300* (score 1.00): "PACIFICAP ENTERTAINMENT shall not now or in the future contest the validity of THE HENRY FILM AND ENTERTAINMENT CORPORATION."
- False alarm in *PFSFUNDS_06_26_2020-EX-99.H OTH MAT CONT-SERVICES AGREEMENT* (score 0.20): "Nothing in this Agreement shall prevent the Adviser or any affiliated person of the Adviser from providing services for any other person, firm or corporation, including other investment companies; provided, however, that the Adviser expressly represents that it will undertake no activities which, in..."
- False alarm in *ON4COMMUNICATIONSINC_07_02_2009-EX-10.1-PROMOTION AGREEMENT* (score 0.58): "In consideration of the fees paid by Sponsor as set out herein, Charity Tunes agrees that during the period beginning October 1, 2009 and ending March 31, 2010, Charity Tunes shall not enable another program sponsorship for all competitive products/product categories distributed/sold within the tota..."
- Wrong quote in *NakedBrandGroupInc_20150731_POS AM (on S-1)_EX-10.75_9196027*: gave "Furthermore, Wade will not engage in any business or other transaction or have any financial or personal interest in any entity whose primary or core business is selling or manufacturing Innerwear dur...", gold starts "Wade represents and warrants that during the Term and in the Territory, neither Wade nor any of his agents, representatives or employees will solicit, initiate, or encourage any proposal for an endors..."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "We will not require you to pay Liquidated Damages unless you or one of your Affiliates own and/or operate a hotel at the Hotel Site under a lease, license or franchise from a Competitor within three (...", gold starts "We may immediately terminate this Agreement on notice to you and without any opportunity to cure the default if:"
- Wrong quote in *ENTERTAINMENTGAMINGASIAINC_02_15_2005-EX-10.5-DISTRIBUTOR AG*: gave "Notwithstanding Section 4.4 of this Agreement, use its best commercial efforts to enter into a separate agreement with Distributor for the manufacture of a gaming chip-sorting machine or the manufactu...", gold starts "4.4. Subject to Section 4.5 of this Agreement, for a period of twenty-four (24) months after the Effective Date, not to develop, manufacture, market, distribute, sell or supply anywhere in the world t..."

## Governing Law

0 missed, 2 false alarms, 1 found with the wrong quote.

- False alarm in *PacificapEntertainmentHoldingsInc_20051115_8-KA_EX-1.01_4300* (score 1.00): "ALL DISPUTES ARISING OUT OF THIS AGREEMENT SHALL BE SETTLED VIA BINDING ARBITRATION ACCORDING TO THE RULES AND REGULATIONS SET FORTH BY THE AMERICAN ARBITRATION ASSOCIATION IN SAN DIEGO COUNTY , THE STATE OF CALIFORNIA."
- False alarm in *TELEGLOBEINTERNATIONALHOLDINGSLTD_03_29_2004-EX-10.10-CONSTR* (score 1.00): "In the performance of their obligations hereunder, the Parties agree to comply with all applicable laws of all Countries having jurisdiction over the activities performed under or stipulated by this Agreement."
- Wrong quote in *CHAPARRALRESOURCESINC_03_30_2000-EX-10.66-TRANSPORTATION CON*: gave "In all other matters not stipulated in this Contract, relations of the Parties shall be governed by the legislation of the Republic of Kazakhstan in force.", gold starts "Effective legislation of the Republic of Kazakhstan shall apply to any relations of the Parties arising out of this Contract."
