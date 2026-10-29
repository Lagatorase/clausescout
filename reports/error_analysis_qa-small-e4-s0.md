# Error analysis: qa-small-e4-s0 (val, threshold 0.1)

Examples are picked at random (seed fixed) so they are not the most flattering or the worst. Quotes are shortened to 300 characters.

## Cap On Liability

1 missed, 20 false alarms, 3 found with the wrong quote.

- Missed in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT *: "In the event the Company terminates this Agreement, the Company shall pay to HDI a termination payment, (the "Termination Payment") the amount of which shall be an amount equal to the aggregate Net Sales for the twelve (12) months preceding the Termination Date less $800,000, the balance of which sh..."
- False alarm in *Principal Life Insurance Company - Broker Dealer Marketing a* (score 0.93): "Broker Dealer understands and agrees that Issuer shall execute telephone transactions only in accordance with the terms and conditions of the then current prospectus applicable to Annuity Contracts and agrees that in consideration for Broker Dealer's right to exercise the telephone transaction servi..."
- False alarm in *BORROWMONEYCOM,INC_06_11_2020-EX-10.1-JOINT VENTURE AGREEMEN* (score 0.33): "The Member will be liable for any and all acts or failures to act resulting from gross negligence or willful misconduct."
- False alarm in *NakedBrandGroupInc_20150731_POS AM (on S-1)_EX-10.75_9196027* (score 0.51): "Naked shall be solely responsible for all liability arising out of production, distribution and sale of its product."
- Wrong quote in *ScansourceInc_20190822_10-K_EX-10.38_11793958_EX-10.38_Distr*: gave "Customer's sole and exclusive remedy and the entire liability of Cisco and its suppliers and licensors under this limited warranty will be, at Cisco's option, repair, replacement, Source: SCANSOURCE, ...", gold starts "Customer's sole and exclusive remedy and the entire liability of Cisco and its suppliers and licensors under this limited warranty will be, at Cisco's option, repair, replacement,"
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "NOTHING IN THIS SECTION LIMITS OUR RIGHT OR THE RIGHT OF AN INDEMNIFIED PARTY TO BE INDEMNIFIED AGAINST THE PAYMENT OF PUNITIVE OR EXEMPLARY DAMAGES TO A THIRD PARTY.", gold starts "THE PARTIES ACKNOWLEDGE THAT LIQUIDATED DAMAGES PAYABLE BY YOU UNDER THIS AGREEMENT (WHETHER PRE-OPENING LIQUIDATED DAMAGES OR LIQUIDATED DAMAGES FOR EARLY TERMINATION) ARE NOT PUNITIVE OR EXEMPLARY D..."
- Wrong quote in *Antares Pharma, Inc. - Manufacturing Agreement*: gave "Provided that (i) AMAG and Antares have agreed to the terms of an Alternate Arrangement, or (ii) AMAG commences purchasing Devices, Components, Products, sample Products and/or Trainers directly from ...", gold starts "The Parties acknowledge and agree that title to and risk of loss of all Prefilled Syringes shall at all times belong to and remain in AMAG; provided that, subject to the limitations on liability set f..."

## Uncapped Liability

0 missed, 26 false alarms, 3 found with the wrong quote.

- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.83): "This Agreement does not provide, and is not intended to be construed or deemed to provide, any policyholder of the Company with recourse to or against any of the assets of AIG."
- False alarm in *GentechHoldingsInc_20190808_1-A_EX1A-6 MAT CTRCT_11776814_EX* (score 1.00): "IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY SPECIAL, INDIRECT, EXEMPLARY OR CONSEQUENTIAL DAMAGES ARISING OUT OF THIS AGREEMENT OR PURCHASE OR USE OF THE PRODUCTS."
- False alarm in *MEETGROUP,INC_06_29_2017-EX-10.1-COOPERATION AGREEMENT* (score 0.38): "Notwithstanding the foregoing, the provisions of this Section 3 shall not limit in any respect the actions of any director of the Company (including, but not limited to, the New Directors) in their capacity as such, recognizing that such actions are subject to such director's fiduciary duties to the..."
- Wrong quote in *FuelcellEnergyInc_20191106_8-K_EX-10.1_11868007_EX-10.1_Deve*: gave "In no event will either Party be liable to the other Party under this Agreement for any consequential, indirect, special, incidental, punitive or exemplary loss or damage, including, without limitatio...", gold starts "Notwithstanding anything to the contrary in this Agreement, each Party will bear full responsibility, without limit, for the following: (i) Gross Negligence or Willful Misconduct attributable to its p..."
- Wrong quote in *BLUEFLYINC_03_27_2002-EX-10.27-e-business Hosting Agreement*: gave "Regardless of the basis on which IBM is entitled to claim damages from Customer (including fundamental breach, negligence, misrepresentation, or other contract or tort claim), Customer is liable for n...", gold starts "In no event will either party be liable to the other for special, incidental, or indirect damages or for any consequential damages (including lost profits or savings), even if they are informed of the..."
- Wrong quote in *PareteumCorp_20081001_8-K_EX-99.1_2654808_EX-99.1_Hosting Ag*: gave "Without prejudice to the provisions expressly stated elsewhere in this Agreement, a Party's liability for damage suffered by the other Party, attributable to the first mentioned Party or a person for ...", gold starts "Limitation of liability as described in this article shall not apply: a) in case the damage or loss is caused by a Party's willful misconduct (including fraud) or gross negligence, or b) in case of a ..."

## Termination For Convenience

0 missed, 23 false alarms, 1 found with the wrong quote.

- False alarm in *GentechHoldingsInc_20190808_1-A_EX1A-6 MAT CTRCT_11776814_EX* (score 0.96): "Distributor shall have the option to renew this Agreement for an additional Three (3) year period by providing prior written notice to Company within Ninety (90) days of the end of the initial period of this Agreement."
- False alarm in *ATHENSBANCSHARESCORP_11_02_2009-EX-1.2-AGENCY AGREEMENT , 20* (score 0.69): "The Agent may terminate this Agreement by giving the notice indicated below in this Section 12 at any time after this Agreement becomes effective as follows:"
- False alarm in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT * (score 0.80): "This Agreement shall be automatically renewed for an additional one year period on each anniversary of the Effective Date, unless terminated by either Party hereto upon ninety (90) days written notice to the other."
- Wrong quote in *ROCKYMOUNTAINCHOCOLATEFACTORY,INC_12_23_2019-EX-10.2-STRATEG*: gave "The Company may impose stop transfer instructions with respect to any Lock-Up Security subject to the foregoing restriction until the end of said one hundred and eighty (180) day or shorter period.", gold starts "If the Farids Group determines for any reason not to proceed with any proposed registration requested pursuant to Section 6.1, the Farids Group shall promptly notify the Company in writing."

## Change Of Control

0 missed, 35 false alarms, 3 found with the wrong quote.

- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.47): "AIG shall have the absolute right to terminate this Agreement upon thirty (30) days' prior written notice to the Company, which notice shall state the effective date of termination (the "Termination Date"); provided, however, that AIG agrees not to terminate this Agreement unless (a) AIG significant..."
- False alarm in *BLUEFLYINC_03_27_2002-EX-10.27-e-business Hosting Agreement* (score 0.95): "Notwithstanding the foregoing, Customer may assign this Agreement to a successor organization by merger, consolidation or acquisition."
- False alarm in *IdeanomicsInc_20160330_10-K_EX-10.26_9512211_EX-10.26_Conten* (score 0.27): "Except as otherwise specified in the previous sentence, Licensee may not sublicense any of its rights under Section 2(a) [License Grant] without Licensor's prior written consent, which shall not be unreasonably withheld or delayed."
- Wrong quote in *CardlyticsInc_20180112_S-1_EX-10.16_11002987_EX-10.16_Mainte*: gave "Bank of America may not unreasonably withhold its consent of assignment in the event the supplier merges or consolidates with another entity.", gold starts "A Termination Event shall have occurred if:"
- Wrong quote in *SLINGERBAGINC_05_27_2020-EX-10.7-CONSULTING AGREEMENT*: gave "For the avoidance of doubt, it is agreed that in the event that the Company participates in a merger, acquisition, restructuring, reorganization or other transaction in which the Company is merged int...", gold starts "Upon any capital reorganization of the Company's capital stock (other than a subdivision, combination, reclassification or exchange of shares provided for elsewhere in this Section 2) or a merger or c..."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "The following Transfers are permitted without giving notice or obtaining our consent if the Permitted Transfer does not result in a change in Control of the Franchisee, the Hotel or the Hotel Site and...", gold starts "We will have sixty (60) days from our receipt of the completed and signed franchise application to consent or withhold our consent to any proposed Change of Ownership Transfer."

## Anti-Assignment

0 missed, 8 false alarms, 1 found with the wrong quote.

- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.59): "AIG shall have the absolute right to terminate this Agreement upon thirty (30) days' prior written notice to the Company, which notice shall state the effective date of termination (the "Termination Date"); provided, however, that AIG agrees not to terminate this Agreement unless (a) AIG significant..."
- False alarm in *GULFSOUTHMEDICALSUPPLYINC_12_24_1997-EX-4-AFFILIATE AGREEMEN* (score 0.48): "The undersigned understands and agrees that"
- False alarm in *ALAMOGORDOFINANCIALCORP_12_16_1999-EX-1-AGENCY AGREEMENT* (score 0.24): "The Agent may terminate this Agreement by giving the notice indicated below in this Section 11 at any time after this Agreement becomes effective as follows:"
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "We may assign or Transfer this Agreement or any of our rights, duties, or assets under this Agreement, by operation of law or otherwise, to any person or legal entity without your consent, provided th...", gold starts "We may immediately terminate this Agreement on notice to you and without any opportunity to cure the default if:"

## Exclusivity

0 missed, 22 false alarms, 3 found with the wrong quote.

- False alarm in *JINGWEIINTERNATIONALLTD_10_04_2007-EX-10.7-INTELLECTUAL PROP* (score 0.73): "Party B agrees not to directly or indirectly use or authorize to use the Intellectual Property in the other regions."
- False alarm in *EUROPEANMICROHOLDINGSINC_03_06_1998-EX-10.6-DISTRIBUTOR AGRE* (score 0.36): "Such remedy will be exclusive and in full satisfaction of Distributor's claims hereunder."
- False alarm in *ROCKYMOUNTAINCHOCOLATEFACTORY,INC_12_23_2019-EX-10.2-STRATEG* (score 0.89): "Each of EA, Farids and the Company shall not, and shall cause their respective controlled Affiliates to not, either directly or indirectly solicit, hire, or contract with any of the employees of the other party or its Affiliates during the Term (as defined in the Exclusive Supplier Operating Agreeme..."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "You will deliver all goods and materials containing the Marks to us and we will have the sole and exclusive use of any items containing the Marks.", gold starts "The only reservation service or system you may use for outgoing reservations referred by or from the Hotel to other Network Hotels will be the Reservation Service or other reservation services we desi..."
- Wrong quote in *AMERICANPHYSICIANSCAPITALINC_03_31_2003-EX-10.26-AGENCY AGRE*: gave "In return for the exclusive appointment of Agency by MICOA to sell its professional liability products listed on the &sbsp;attached Commission Schedule in Nevada, Agency agrees not to sell any competi...", gold starts "In order to allow SC&W to expand the distribution system in Nevada with select and controlled subagents, an exclusive agency agreement will be negotiated which will spell out the terms and conditions ..."
- Wrong quote in *AMERICASSHOPPINGMALLINC_12_10_1999-EX-10.2-SITE DEVELOPMENT *: gave "Except as provided in Section 6.2, during the term of this Agreement, the Company shall not participate in any project similar to the Site on the Internet with respect to Deerskin Products or products...", gold starts "HDI shall have the exclusive right to use of the "Deerskin" brand for a self-contained web site for the offering of Deerskin Products directly to the consumer on the Internet."

## Non-Compete

0 missed, 28 false alarms, 3 found with the wrong quote.

- False alarm in *MEETGROUP,INC_06_29_2017-EX-10.1-COOPERATION AGREEMENT* (score 0.63): "Each Investor agrees that, from the date of this Agreement until the expiration of the Standstill Period (as defined below), without the prior written consent of a majority of the Board specifically expressed in a written resolution, neither it nor any of its Related Persons (as defined herein) will..."
- False alarm in *VARIABLESEPARATEACCOUNT_04_30_2014-EX-13.C-UNCONDITIONAL CAP* (score 0.58): "AIG shall have the absolute right to terminate this Agreement upon thirty (30) days' prior written notice to the Company, which notice shall state the effective date of termination (the "Termination Date"); provided, however, that AIG agrees not to terminate this Agreement unless (a) AIG significant..."
- False alarm in *ON2TECHNOLOGIES,INC_11_17_2006-EX-10.3-SUPPORT AND MAINTENAN* (score 0.42): "As consideration for the services to be provided by Wildform hereunder, On2 will pay Wildform a total of (i) $160,000 payable as follows: (a) $22,500 per month for each of the four (4) months following the Effective Date and $10,000 per month for each of the fifth and sixth months following the Effe..."
- Wrong quote in *GAINSCOINC_01_21_2010-EX-10.41-SPONSORSHIP AGREEMENT*: gave "Racing agrees that, during the term of this Agreement, (i) Sponsor shall have the right to approve or disapprove any additional sponsor identified by Racing, and (ii) unless another proposed sponsor h...", gold starts "Subject to payment by the Sponsor of the sponsorship fee provided for herein, during the term of this Agreement Racing shall cause the Racing Team to provide for the Sponsor's benefit all of the benef..."
- Wrong quote in *ENTERTAINMENTGAMINGASIAINC_02_15_2005-EX-10.5-DISTRIBUTOR AG*: gave "Notwithstanding Section 4.4 of this Agreement, use its best commercial efforts to enter into a separate agreement with Distributor for the manufacture of a gaming chip-sorting machine or the manufactu...", gold starts "4.4. Subject to Section 4.5 of this Agreement, for a period of twenty-four (24) months after the Effective Date, not to develop, manufacture, market, distribute, sell or supply anywhere in the world t..."
- Wrong quote in *HOSPITALITYINVESTORSTRUST,INC_04_07_2014-EX-10.26-FRANCHISE *: gave "We will not require you to pay Liquidated Damages unless you or one of your Affiliates own and/or operate a hotel at the Hotel Site under a lease, license or franchise from a Competitor within three (...", gold starts "We may immediately terminate this Agreement on notice to you and without any opportunity to cure the default if:"

## Governing Law

0 missed, 2 false alarms, 1 found with the wrong quote.

- False alarm in *PacificapEntertainmentHoldingsInc_20051115_8-KA_EX-1.01_4300* (score 0.99): "ALL DISPUTES ARISING OUT OF THIS AGREEMENT SHALL BE SETTLED VIA BINDING ARBITRATION ACCORDING TO THE RULES AND REGULATIONS SET FORTH BY THE AMERICAN ARBITRATION ASSOCIATION IN SAN DIEGO COUNTY , THE STATE OF CALIFORNIA."
- False alarm in *TELEGLOBEINTERNATIONALHOLDINGSLTD_03_29_2004-EX-10.10-CONSTR* (score 0.99): "In the performance of their obligations hereunder, the Parties agree to comply with all applicable laws of all Countries having jurisdiction over the activities performed under or stipulated by this Agreement."
- Wrong quote in *CHAPARRALRESOURCESINC_03_30_2000-EX-10.66-TRANSPORTATION CON*: gave "In all other matters not stipulated in this Contract, relations of the Parties shall be governed by the legislation of the Republic of Kazakhstan in force.", gold starts "Effective legislation of the Republic of Kazakhstan shall apply to any relations of the Parties arising out of this Contract."
