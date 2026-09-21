"""Script to generate a 27-topic controlled synthetic motor insurance document corpus.
All documents are strictly marked as synthetic/demo test documents for university and demo purposes.
"""

from __future__ import annotations
from pathlib import Path

TARGET_DIR = Path(__file__).parents[1] / "data" / "policy_docs"

DOCUMENTS = [
    {
        "filename": "synthetic_collision_claims.txt",
        "title": "Motor Insurance - Vehicle Collision Claims Guide",
        "topic": "vehicle_collision",
        "incident_type": "vehicle_collision",
        "version": "1.0",
        "content": """# Motor Insurance - Vehicle Collision Claims Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=vehicle_collision, incident_type=vehicle_collision, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide outlines standard procedures, paperwork, and requirements for motor vehicle collision claims. It applies to private cars, commercial vans, utility vehicles, and motorcycles covered under comprehensive motor insurance policies in our demonstration environment.

Section 2: When This Applies
This guidance applies whenever an insured vehicle is involved in a road traffic accident, crash, smash, collision, or physical impact. Scenarios include:
- Collision with another motor vehicle (head-on collision, rear-end impact, T-bone, or side swipe)
- Impact with stationary objects such as walls, lamp posts, road barriers, or trees
- Multi-vehicle pileups and chain-reaction accidents
- Rollover accidents and ditch impacts
Colloquial customer descriptions such as "I had a car crash", "I collided with another vehicle", "my car was smashed", or "fender bender" fall under this collision policy scope.

Section 3: Required Documents
To process a vehicle collision claim, the policyholder or driver must submit the following core documents:
- Completed motor claim form detailing the date, time, location, and circumstances of the crash
- Itemized repair estimate or garage quotation from an authorized repair workshop
- High-resolution damage photographs showing the damaged vehicle parts, overall vehicle view, and license plate
- Valid driving licence copy of the person operating the vehicle during the accident
- Vehicle registration document (certificate of registration / revenue license)
- Official police report or police accident entry if another vehicle was involved, injuries occurred, or dispute exists

Section 4: Optional and Conditional Documents
Depending on the specific collision circumstances, the following additional documentation may be requested:
- Third-party driver details, vehicle registration numbers, and third-party insurer information
- Contact information of independent eyewitnesses present at the accident scene
- Dashcam footage or CCTV video recording of the collision
- Towing receipt or vehicle recovery invoice if the car was immobile and required towing

Section 5: Claim Procedure and Steps
1. Immediate safety: Move to a safe location, turn on hazard lights, and ensure no persons require emergency medical care.
2. Photographic evidence: Take photographs of both vehicles in their post-impact positions before moving them.
3. Police notification: Notify local police if required by law or if significant property damage or injury occurred.
4. Claim lodgment: Submit the initial claim notification promptly (within 24 to 48 hours of the incident).
5. Document upload: Upload all required repair quotations, license copies, registration papers, and photos.
6. Inspection: An insurance assessor or technical loss adjuster will inspect the vehicle damage before repairs begin.

Section 6: Important Notes and Practical Guidance
- Deductible / Policy Excess: The standard policy collision excess applies to own-damage repairs unless third-party fault is fully proven and accepted by the other driver's insurer.
- Unauthorized Repairs: Do not dismantle or authorize repair work prior to official vehicle inspection and repair authorization.
- Prompt Reporting: Delay in reporting without reasonable cause may delay assessment or require additional review.

Section 7: Limitations and Human Review
Automated triage systems and retrieval agents assist with document verification and information retrieval. All final claim determinations, settlement authorizations, and coverage decisions are made solely by an authorized human claims officer.
"""
    },
    {
        "filename": "synthetic_windscreen_glass_claims.txt",
        "title": "Motor Insurance - Windscreen and Glass Damage Guide",
        "topic": "windscreen_damage",
        "incident_type": "windscreen_damage",
        "version": "1.0",
        "content": """# Motor Insurance - Windscreen and Glass Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=windscreen_damage, incident_type=windscreen_damage, synthetic=true, version=1.0]

Section 1: Scope and Application
This document provides guidelines for claiming repair or replacement of damaged vehicle glass under comprehensive motor insurance coverage. It covers front windscreens, rear windshields, side window glass, quarter glass, and manufacturer-installed sunroof glass.

Section 2: When This Applies
This policy section applies when vehicle glass suffers accidental damage without major structural vehicle bodywork damage. Typical occurrences include:
- Flying gravel or stones thrown up by other vehicles cracking or chipping the windscreen
- Sudden temperature fluctuations or stress cracks developing across the glass
- Falling branches, hail, or debris cracking the glass
- Glass shattered during an attempted theft or vandalism incident
Customer expressions such as "my windscreen broke", "stone chip on windshield", "cracked front glass", "window shattered", or "glass broken what paper i need" apply here.

Section 3: Required Documents
The following papers and evidence are required when filing a windscreen or glass claim:
- Clear photographs of the glass damage showing the crack or chip in detail, with at least one wide photo showing the vehicle license plate
- Official repair or replacement estimate from a certified glass fitter or automotive repairer
- Copy of the vehicle registration document confirming the vehicle make and model
- Valid driving licence of the policyholder or regular driver
- Completed online claim submission form specifying the date and approximate location of damage

Section 4: Optional and Conditional Documents
- Police report: Generally NOT required for accidental stone chip or road debris glass damage. A police report is required ONLY if the glass was broken during an intentional break-in, theft, or criminal vandalism.
- Invoices: Final paid invoice and proof of payment if emergency glass replacement was authorized under approved provider terms.

Section 5: Claim Procedure and Steps
1. Photograph the damage immediately: Take clear close-ups showing the extent of crack propagation.
2. Determine repair vs replacement: Chips smaller than a coin can often be resin-repaired without replacing the entire windscreen.
3. Submit claim: Log into the customer portal and submit damage photos along with the repair estimate.
4. Glass specialist booking: Use an approved windscreen installer network partner for seamless direct billing.

Section 6: Important Notes and Practical Guidance
- No Claim Discount (NCD) Protection: In many comprehensive policies, an isolated windscreen claim does not affect your accrued No Claim Bonus/Discount, provided no body panel repairs are claimed.
- Glass Excess: A specialized glass deductible or excess may apply as specified in your policy schedule.

Section 7: Limitations and Human Review
This guidance serves as an advisory demonstration. Coverage validity is verified against your individual policy schedule by an authorized claims officer.
"""
    },
    {
        "filename": "synthetic_theft_breakin_claims.txt",
        "title": "Motor Insurance - Vehicle Theft and Break-In Guide",
        "topic": "theft_claims",
        "incident_type": "theft",
        "version": "1.0",
        "content": """# Motor Insurance - Vehicle Theft and Break-In Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=theft_claims, incident_type=theft, synthetic=true, version=1.0]

Section 1: Scope and Application
This document sets out the mandatory procedure, evidence, and requirements for reporting total vehicle theft, attempted vehicle theft, vehicle break-ins, and theft of installed motor parts.

Section 2: When This Applies
This guidance applies under comprehensive and third-party fire & theft policies when:
- The entire motor vehicle has been stolen from a parking area, street, driveway, or garage
- A vehicle break-in occurred resulting in forced entry, broken door locks, or broken windows
- Vehicle components such as wheels, alloy rims, catalytic converters, batteries, or head units were stolen
- A carjacking or robbery occurred
Common customer inquiries include "someone stole my car", "my car was stolen what documents are needed", "vehicle break in what papers", or "car theft claim process".

Section 3: Required Documents
Due to the serious nature of theft claims, the following verified documents are strictly required:
- Certified police report / police complaint extract from the police station where the theft was reported
- Completed theft claim statement form with chronological account of when the vehicle was last seen
- Original vehicle registration certificate (logbook / certificate of ownership)
- Copy of the policyholder's national identity card (NIC) or passport
- Copy of the driving licence of the person who last drove the vehicle
- All sets of vehicle keys (including spare keys) surrendered to the insurer or detailed explanation if unavailable
- Purchase receipt, invoice, or vehicle valuation report if requested

Section 4: Optional and Conditional Documents
- CCTV surveillance footage or security logbook entries from the premises where the theft took place
- Repair estimate for damaged locks, ignition switch, or glass in the event of an attempted theft or recovered stolen vehicle
- Inventory of stolen aftermarket accessories with original purchase receipts

Section 5: Claim Procedure and Steps
1. Report to Police immediately: Within 2 to 4 hours of discovering the theft, lodge a formal police complaint.
2. Obtain Police reference: Request the official crime reference number or extract copy.
3. Notify Insurer: Submit initial claim notice within 24 hours to prevent unauthorized use liabilities.
4. Key surrender and interview: Surrender all vehicle keys and cooperate with the claims investigator.
5. Statutory waiting period: A standard 30 to 45 day tracing period applies before unrecovered vehicles are declared total loss.

Section 6: Important Notes and Practical Guidance
- Anti-Theft Precautions: Claims may be subject to review if keys were left in an unattended vehicle or if windows were left open.
- Tracking Devices: If the vehicle is equipped with GPS tracking, notify the tracking company immediately upon discovery.

Section 7: Limitations and Human Review
All theft claims undergo mandatory investigative scrutiny and fraud risk verification. The final claim decision is made exclusively by an authorized human claims officer.
"""
    },
    {
        "filename": "synthetic_flood_water_damage_claims.txt",
        "title": "Motor Insurance - Flood and Water Damage Guide",
        "topic": "flood_damage",
        "incident_type": "flood_damage",
        "version": "1.0",
        "content": """# Motor Insurance - Flood and Water Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=flood_damage, incident_type=flood_damage, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains claim submission requirements for motor vehicles damaged by floods, torrential rain, rising water, inundation, river overflow, or flash flooding.

Section 2: When This Applies
Applies when water enters the vehicle cabin, engine compartment, transmission, or electrical systems due to natural flooding or heavy storm runoff. Common user queries:
- "flood damaged my car what should i provide"
- "flood dmg claim what should i upload"
- "water entered engine what papers needed"
- "car was parked in flooded street"
- "rising flood water submerged vehicle"

Section 3: Required Documents
The following documentation must be uploaded for flood damage claim assessment:
- Detailed photographs showing water immersion levels (water marks on wheels, doors, upholstery, and dashboard)
- Professional repair estimate from an authorized garage itemizing mechanical, electrical, and upholstery remediation
- Completed motor claim form stating the exact geographic location, street name, and time of flooding
- Copy of the vehicle registration document confirming ownership
- Valid driving licence copy of the vehicle owner or driver

Section 4: Optional and Conditional Documents
- Local meteorological department advisory or newspaper weather clipping confirming flash floods in the area
- Towing and recovery service invoice for transporting the submerged vehicle to the garage
- Diagnostic scan report from the mechanic regarding electronic control unit (ECU) water immersion

Section 5: Claim Procedure and Steps
1. CRITICAL SAFETY RULE: DO NOT ATTEMPT TO START THE ENGINE if the vehicle has been submerged in flood water. Starting a wet engine causes catastrophic hydrostatic lock.
2. Disconnect battery: Disconnect battery terminals safely if accessible to prevent short circuits.
3. Photograph: Take photos of the vehicle in the water and water lines inside and outside the car.
4. Tow to workshop: Have the vehicle towed to a qualified repair facility for drying and diagnostic assessment.
5. Submit claim: File the claim online attaching all photos and garage diagnostics.

Section 6: Important Notes and Practical Guidance
- Hydrostatic Lock Exclusions: Starting an engine in standing floodwater may be categorized as avoidable consequential damage and excluded from payout unless specific natural disaster coverage covers it.
- Special Perils Endorsement: Verify that your policy schedule includes natural perils / flood cover endorsements.

Section 7: Limitations and Human Review
Automated tools assist with cataloging evidence. Human claims officers assess whether policy endorsements cover flood events and authorize appropriate repair or total-loss settlements.
"""
    },
    {
        "filename": "synthetic_fire_damage_claims.txt",
        "title": "Motor Insurance - Fire and Explosion Damage Guide",
        "topic": "fire_damage",
        "incident_type": "fire_damage",
        "version": "1.0",
        "content": """# Motor Insurance - Fire and Explosion Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=fire_damage, incident_type=fire_damage, synthetic=true, version=1.0]

Section 1: Scope and Application
This document provides guidelines for vehicle damage resulting from accidental fire, engine combustion, electrical short circuit, lightning, external wildfire, or explosion.

Section 2: When This Applies
Applies under comprehensive and third-party fire & theft policies when a vehicle catches fire or suffers scorch, heat, or smoke damage. Scenarios:
- Engine compartment fire caused by mechanical or electrical malfunction
- External fire spreading from an adjacent structure, garage, or vehicle
- Wildfire or bushfire encroaching on a parked or traveling vehicle
- Malicious arson or explosive damage

Section 3: Required Documents
The following papers are required for fire claims:
- Fire Brigade incident report or official municipal fire department investigation certificate
- Official police station report recording the fire incident
- Clear photographs of the burnt vehicle showing all angles, chassis numbers, and burnt areas
- Vehicle registration book (certificate of registration)
- Valid driving licence of the owner or last driver
- Itemized repair estimate or salvage evaluation from an authorized technical assessor

Section 4: Optional and Conditional Documents
- Forensic or technical expert report on cause of fire origin (arson vs electrical short circuit)
- Towing and salvage transport receipts
- Property damage claims from third parties if the vehicle fire damaged external structures

Section 5: Claim Procedure and Steps
1. Extinguish and ensure safety: Ensure personal safety and alert emergency fire services immediately.
2. Do not disturb debris: Avoid tampering with electrical wiring or burnt components before inspection.
3. Obtain fire service documentation: Secure the fire incident log reference from the responding station.
4. Lodge claim: Submit claim form and photos within 24 hours of the incident.

Section 6: Important Notes and Practical Guidance
- Arson and Fraud Checks: Unexplained vehicle fires undergo technical origin investigation.
- Total Loss Settlement: Severe fires resulting in destroyed wiring harnesses and structural warping are typically settled on a constructive total loss basis according to market valuation.

Section 7: Limitations and Human Review
All fire damage claims require technical adjuster review and authoritative evaluation by a human claims officer.
"""
    },
    {
        "filename": "synthetic_vandalism_damage_claims.txt",
        "title": "Motor Insurance - Vandalism and Malicious Damage Guide",
        "topic": "vandalism",
        "incident_type": "vandalism",
        "version": "1.0",
        "content": """# Motor Insurance - Vandalism and Malicious Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=vandalism, incident_type=vandalism, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide outlines the claims process for intentional, malicious, or criminal damage inflicted upon an insured motor vehicle by third parties without the owner's consent.

Section 2: When This Applies
Applies when a vehicle has been deliberately damaged while parked or in transit. Common examples:
- Keyed paintwork or scratched vehicle body panels
- Slashed or punctured tires
- Broken side mirrors, smashed headlights, or shattered glass caused by vandals
- Graffiti, paint spraying, or deliberate denting of panels
- Broken antennas or ripped wipers

Section 3: Required Documents
The following documents are mandatory for vandalism claims:
- Official police entry or crime incident report documenting the malicious act
- High-resolution photographs clearly displaying all vandalized surfaces and vehicle registration plate
- Workshop repair estimate for repainting, panel repair, or parts replacement
- Vehicle registration certificate confirming ownership
- Driving licence copy of the policyholder
- Completed claim form stating date, location, and circumstances when damage was observed

Section 4: Optional and Conditional Documents
- CCTV security camera recordings from surrounding buildings or parking facilities
- Statements from eyewitnesses or building security personnel
- Previous maintenance or inspection records showing pristine condition prior to incident

Section 5: Claim Procedure and Steps
1. Preserve evidence: Do not attempt to polish out scratches or wash away paint before photographing.
2. Report to police: File an entry at the local police station to obtain a criminal damage reference.
3. Upload documents: Submit the claim form, photos, repair quote, and police report online.
4. Assessor inspection: Allow an insurer adjuster to verify the damage pattern against the reported incident.

Section 6: Important Notes and Practical Guidance
- Deductible: Standard policy excess applies to malicious damage claims unless an identified third-party perpetrator is apprehended and convicted.
- Single Incident Rule: Vandalism occurring on separate dates cannot be combined into a single claim.

Section 7: Limitations and Human Review
AI systems assist with document intake. A human claims officer examines the police report, verifies policy coverage, and determines claim approval.
"""
    },
    {
        "filename": "synthetic_third_party_damage_claims.txt",
        "title": "Motor Insurance - Third-Party Damage and Liability Guide",
        "topic": "third_party_damage",
        "incident_type": "third_party_damage",
        "version": "1.0",
        "content": """# Motor Insurance - Third-Party Damage and Liability Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=third_party_damage, incident_type=third_party_damage, synthetic=true, version=1.0]

Section 1: Scope and Application
This document provides guidance when an insured vehicle is involved in an incident causing damage to third-party property, vehicles, or structures.

Section 2: When This Applies
Applies when your vehicle causes damage to:
- Another motorist's car, van, truck, or motorcycle
- Public or municipal infrastructure (light posts, guard rails, traffic signals)
- Private third-party property (residential gates, boundary walls, shop fronts)
- Stationary parked vehicles or roadside fixtures

Section 3: Required Documents
To process third-party damage claims and protect against unverified liability, submit:
- Completed motor claim form giving a full, factual description of the incident
- Official police accident report documenting all involved parties and vehicle license numbers
- Driving licence copy of the authorized driver operating the vehicle at the time
- Vehicle registration certificate
- Clear photographs of the accident scene showing damage to both your vehicle and third-party property
- Contact details and registration numbers of the third-party vehicle owner and their insurer

Section 4: Optional and Conditional Documents
- Third-party repair quote or letter of claim sent by the third party or their insurance company
- Dashcam footage showing the trajectory and relative positions of all vehicles
- Contact details of independent witnesses

Section 5: Claim Procedure and Steps
1. Do NOT admit liability: Never admit fault, sign private liability agreements, or promise cash settlements at the accident scene.
2. Exchange details: Record the other driver's full name, telephone number, vehicle registration number, and insurance provider.
3. Police entry: Ensure police take an official report at the scene.
4. Notify insurer promptly: Forward any letters, summons, or third-party communications immediately to your insurer.

Section 6: Important Notes and Practical Guidance
- Legal Representation: Your motor policy provides legal defense against unmerited third-party claims.
- Knock-for-Knock Agreements: In many jurisdictions, insurers handle reciprocal claims through established inter-insurer agreements.

Section 7: Limitations and Human Review
Third-party liability claims require rigorous legal and factual scrutiny. Authorized claims officers and legal adjudicators evaluate fault and approve settlements.
"""
    },
    {
        "filename": "synthetic_hit_and_run_claims.txt",
        "title": "Motor Insurance - Hit-and-Run Incident Guide",
        "topic": "hit_and_run",
        "incident_type": "hit_and_run",
        "version": "1.0",
        "content": """# Motor Insurance - Hit-and-Run Incident Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=hit_and_run, incident_type=hit_and_run, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains procedures for claiming vehicle damage caused by an unidentified or fleeing vehicle where the responsible third party cannot be located at the scene.

Section 2: When This Applies
Applies in situations where:
- Another vehicle crashed into yours and fled the scene without stopping or exchanging particulars
- Your parked vehicle was struck by an unknown driver who left no note or contact information
- An unidentified vehicle caused a collision and could not be traced by local police

Section 3: Required Documents
Because the third party is unknown, the following documents are mandatory:
- Official police report confirming a hit-and-run incident was reported immediately
- Detailed damage photographs showing paint transfer marks, impact depth, and vehicle registration
- Itemized repair quotation from an authorized body repair garage
- Copy of valid driving licence of the insured or driver
- Vehicle registration book confirming ownership
- Completed claim form stating exact date, time, and location of the incident

Section 4: Optional and Conditional Documents
- CCTV video footage from nearby shops, toll gates, or traffic surveillance cameras
- Dashcam recordings capturing the fleeing vehicle make, model, color, or partial license plate
- Witness testimony or statements taken by investigating police officers

Section 5: Claim Procedure and Steps
1. Report immediately to police: Hit-and-run incidents MUST be reported to the nearest police station within 24 hours.
2. Document paint transfer: Photograph any paint rub-off or debris left by the offending vehicle.
3. Check for cameras: Look for local security cameras overlooking the impact location.
4. Submit claim online: Upload all documents and police report number for rapid triage.

Section 6: Important Notes and Practical Guidance
- Policy Excess: Because the offending driver cannot be identified to recover costs, the standard own-damage policy excess applies unless third-party identity is later uncovered.
- Investigation: Insurers may conduct investigation to corroborate impact marks with reported hit-and-run details.

Section 7: Limitations and Human Review
Claims officers review hit-and-run submissions to confirm damage patterns are consistent with impact evidence before authorizing claim settlement.
"""
    },
    {
        "filename": "synthetic_parking_damage_claims.txt",
        "title": "Motor Insurance - Parking and Stationary Damage Guide",
        "topic": "parking_damage",
        "incident_type": "parking_damage",
        "version": "1.0",
        "content": """# Motor Insurance - Parking and Stationary Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=parking_damage, incident_type=parking_damage, synthetic=true, version=1.0]

Section 1: Scope and Application
This document provides guidelines for claiming minor and moderate damage sustained while a motor vehicle was lawfully parked or stationary.

Section 2: When This Applies
Applies when vehicle damage occurs in:
- Commercial car parks, supermarket parking lots, or underground parking bays
- Curbside on-street parking areas
- Driveways, residential parking spaces, or parking garages
Common scenarios include door ding damage, scraped bumpers from maneuvering vehicles, scratched quarter panels, or shopping trolley impacts.

Section 3: Required Documents
The following papers must be submitted for parking damage claims:
- Photographs of the damage taken in the parking bay, showing the vehicle's position, surroundings, and number plate
- Itemized garage repair estimate for panel beating, dent repair, and repainting
- Vehicle registration document
- Valid driving licence copy of the policyholder
- Completed claim submission form detailing the parking venue, date, and discovery time

Section 4: Optional and Conditional Documents
- Incident log or confirmation slip from commercial parking lot security or mall management
- Police report: Recommended if damage is extensive or if third-party dispute exists; may be waived for minor low-value car park scrapes
- Third-party contact details if the other driver was identified or left a note

Section 5: Claim Procedure and Steps
1. Do not move car immediately: Take wide-angle photos of the car parked in the bay before driving away.
2. Inquire with security: Ask parking attendants if incident logs or security cameras recorded the impact.
3. Get repair estimate: Obtain a quotation from an approved body shop.
4. Submit claim: File via the web portal attaching parking photos and repair estimates.

Section 6: Important Notes and Practical Guidance
- Policy Excess Comparison: Check whether the cost of repairing minor parking dents is lower than your policy excess before claiming.
- Multiple Damages: Pre-existing scratches from unrelated incidents cannot be bundled into a single parking claim.

Section 7: Limitations and Human Review
Claims assessors inspect parking scrape claims to verify paint consistency. Final decisions are made by authorized claims personnel.
"""
    },
    {
        "filename": "synthetic_natural_disaster_claims.txt",
        "title": "Motor Insurance - Natural Disaster and Storm Damage Guide",
        "topic": "natural_disaster",
        "incident_type": "natural_disaster",
        "version": "1.0",
        "content": """# Motor Insurance - Natural Disaster and Storm Damage Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=natural_disaster, incident_type=natural_disaster, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide covers vehicle loss or physical damage resulting from severe natural events, weather catastrophes, and acts of nature.

Section 2: When This Applies
Applies under comprehensive motor policies with natural perils cover when damage is caused by:
- Cyclones, typhoons, gales, hurricanes, and severe windstorms
- Falling trees, collapsing heavy tree limbs, or flying storm debris
- Hailstorms resulting in roof, hood, or windshield denting
- Landslides, mudslides, earthslips, or rockfalls
- Lightning strikes directly affecting electrical systems
- Earthquakes and tsunami inundation

Section 3: Required Documents
The following documentation is necessary to process natural calamity claims:
- Comprehensive photographs showing the fallen object (e.g., tree on car) or weather damage in situ
- Repair estimate from an authorized garage or total loss evaluation from an assessor
- Vehicle registration document
- Copy of the driving licence of the insured
- Completed claim form stating exact time, geographic location, and weather conditions

Section 4: Optional and Conditional Documents
- Local disaster management authority certificate or national meteorological office storm bulletin
- Tree removal service receipt or municipal emergency service report
- Towing invoice for recovery from storm-affected zone

Section 5: Claim Procedure and Steps
1. Ensure personal safety: Do not approach vehicles entangled with downed electrical power lines.
2. Photograph before clearing: Take photos before municipal teams cut away fallen trees or limbs.
3. Mitigate further loss: Cover broken windows with tarpaulin to prevent internal rain damage once safe.
4. Lodge claim: Submit online claim with storm photos and quotation.

Section 6: Important Notes and Practical Guidance
- Policy Endorsements: Ensure "Special Perils" or "Natural Disaster Extension" is active on your policy schedule.
- Total Loss Threshold: Vehicles crushed by mature trees are often evaluated for total loss constructive settlement.

Section 7: Limitations and Human Review
Claims officers examine natural peril endorsements and verify disaster reports before authorizing payouts.
"""
    },
    {
        "filename": "synthetic_required_claim_documents.txt",
        "title": "Motor Insurance - Required Claim Documents Master Checklist",
        "topic": "claim_documents",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Required Claim Documents Master Checklist
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=claim_documents, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This master checklist summarizes all necessary papers, documentation, records, and evidence required when lodging any motor insurance claim.

Section 2: When This Applies
Applies to all policyholders seeking to understand what documents, papers, or files must be provided after an incident. Relevant user queries include:
- "what documents do i need after a crash"
- "papers needed for accident claim"
- "what docs do i need to upload"
- "required paperwork for motor claim"
- "checklist of claim documents"

Section 3: Mandatory Core Documents Checklist
Every claim submission requires the following essential documents:
1. Completed Claim Form: Online submission detailing driver, date, time, location, and accident narrative.
2. Valid Driving Licence: Clear copy of both sides of the driving license of the person who drove the vehicle.
3. Vehicle Registration Certificate: Copy of vehicle registration book / logbook confirming ownership and chassis details.
4. Detailed Repair Estimate: Itemized quotation from a recognized garage listing replacement parts, paint, and labor costs.
5. Damage Photographs: Multiple well-lit photographs displaying full vehicle, damaged areas, and number plates.

Section 4: Conditional Documents (Incident-Specific)
- Police Report: Mandatory for theft, hit-and-run, injuries, third-party disputes, or municipal property damage.
- Third-Party Information: License numbers, driver names, and insurer details when multiple vehicles collide.
- Fire Brigade Report: Mandatory for fire or explosion incidents.
- Weather Bulletins: Required when substantiating major flood or storm damage.
- Surrendered Keys: Mandatory for unrecovered vehicle theft claims.

Section 5: Document Quality and Upload Standards
- File formats: PDF, PNG, JPG, or JPEG formats are supported.
- File size: Files should be clearly legible and under 10MB per document.
- Authenticity: Altered, cropped, or filtered images will be flagged and rejected for manual review.

Section 6: Important Notes and Practical Guidance
- Missing Documents: If mandatory documents are omitted, your claim status remains "awaiting_documents" until supplied.
- Digital Storage: Keep original hard copies of repair bills and police receipts until settlement is finalized.

Section 7: Limitations and Human Review
Automated retrieval checks document completeness, but validity and authenticity are verified by a human claims officer.
"""
    },
    {
        "filename": "synthetic_police_report_requirements.txt",
        "title": "Motor Insurance - Police Report Requirements and Procedures",
        "topic": "police_report",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Police Report Requirements and Procedures
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=police_report, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide clarifies when an official police report, police station entry, or accident report book (ARB) extract is legally and procedurally required for a motor claim.

Section 2: When This Applies
Relevant to customers asking:
- "do i need a police report"
- "is police complaint mandatory for my claim"
- "can i claim without a police report"
- "when is police entry required"

Section 3: When a Police Report is Strictly MANDATORY
A certified police report must be obtained and submitted in the following situations:
- Theft of vehicle or attempted vehicle theft / burglary
- Hit-and-run accidents where the other party fled the scene
- Any collision involving bodily injury, fatality, or hospitalization of any person
- Collisions involving government vehicles, road furniture, or public property
- Incidents involving suspected criminal acts, malicious vandalism, or arson
- Major multi-vehicle crashes with disputed liability

Section 4: When a Police Report May Be WAIVED (Optional)
A police report may be excused or waived under specific conditions:
- Minor single-vehicle accidental damage (e.g. scraping a private gate post or parking pillar)
- Isolated windscreen chips or glass cracks caused by road stones
- Minor stationary parking dents where insurer on-site inspection was completed

Section 5: Procedure for Obtaining a Police Report
1. Visit local station: Go to the traffic police division nearest to the incident location within 24 hours.
2. Record statement: Provide an accurate, truthful statement of the events.
3. Request certified copy: Obtain the official entry number and request a certified copy of the accident book extract.
4. Upload to portal: Upload the scanned police report or receipt voucher during claim filing.

Section 6: Important Notes and Practical Guidance
- Do not make false statements: Discrepancies between police reports and insurance claim forms create severe fraud red flags.
- Time Limit: Most traffic police departments require accidents to be reported within 24 hours of occurrence.

Section 7: Limitations and Human Review
Police report extracts are evaluated by claims adjudicators to confirm accident facts and establish third-party liability.
"""
    },
    {
        "filename": "synthetic_driving_licence_requirements.txt",
        "title": "Motor Insurance - Driving Licence Requirements Guide",
        "topic": "driving_licence",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Driving Licence Requirements Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=driving_licence, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document specifies requirements regarding the driver's licence of the person operating an insured vehicle during an incident.

Section 2: When This Applies
Applies to questions such as:
- "do i need my driving licence"
- "whose driving licence do i submit"
- "what if driver was not the policyholder"
- "expired licence claim validity"

Section 3: Core Requirements
- Valid authorization: The person driving at the moment of the accident must hold a valid, unexpired driver's licence authorized for that vehicle class (e.g., motor car, heavy vehicle, or motorcycle).
- Document submission: Submit a clear scanned copy or photograph of both the front and reverse sides of the driving licence.
- Driver identity: The driver listed on the claim form must match the driver recorded in the police entry (if applicable).

Section 4: Driver Types and Policy Conditions
- Policyholder Driving: Standard copy of policyholder licence required.
- Named Drivers: If policy is restricted to named drivers, the driver must appear on the policy schedule.
- Open Driver Policy: Any driver holding a valid licence who drove with the policyholder's permission is covered.
- Learner Drivers: A learner permit holder must be accompanied by a fully licensed driver pursuant to national traffic laws.

Section 5: Exclusions and License Disqualifications
Claims will be declined if at the time of the incident the driver:
- Held no valid driving licence or had their licence suspended/revoked by a court
- Was driving a vehicle class outside their licensed authorization
- Was driving under the influence of alcohol, narcotics, or intoxicating drugs

Section 6: Important Notes and Practical Guidance
- Renewals: If your licence expired immediately prior to the incident, proof of renewal application may be considered.
- Legibility: Ensure the license number, photo, expiry date, and vehicle classes are clearly legible.

Section 7: Limitations and Human Review
The validity and authenticity of driving credentials are independently verified by human claims adjudicators.
"""
    },
    {
        "filename": "synthetic_vehicle_registration_requirements.txt",
        "title": "Motor Insurance - Vehicle Registration and Ownership Documents Guide",
        "topic": "vehicle_registration",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Vehicle Registration and Ownership Documents Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=vehicle_registration, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document outlines vehicle registration requirements and proof of insurable interest required for motor insurance claims.

Section 2: When This Applies
Applies when verifying vehicle identity, ownership, roadworthiness, and insurable interest during claim processing.

Section 3: Required Registration Documents
Policyholders must submit:
- Certificate of Registration (Registration Book / Logbook / Title Document)
- Current valid Revenue License / Vehicle Road Tax disc
- Periodic vehicle roadworthiness or inspection certificate (for commercial vehicles or aged private vehicles)

Section 4: Vehicle Identification Verification
The registration document must confirm:
- Registered vehicle registration number (license plate)
- Chassis number (VIN) matching the physical vehicle stamping
- Engine number matching the vehicle engine
- Registered vehicle owner name corresponding to the policyholder or an authorized corporate entity

Section 5: Transfer of Ownership and Leased Vehicles
- Recently Purchased Vehicles: If ownership was recently transferred, submit the official transfer acknowledgement or sales agreement.
- Financed / Leased Vehicles: If the vehicle is leased, settlements may require concurrence from the financing financial institution.

Section 6: Important Notes and Practical Guidance
- Keep copies handy: Store digital scans of your vehicle registration to expedite claim processing.
- Engine Modifications: Unauthorized engine replacements not updated on the registration book can jeopardize claim approval.

Section 7: Limitations and Human Review
Claims officers cross-verify registration records against insurance policy databases before approving repair authorizations.
"""
    },
    {
        "filename": "synthetic_damage_photographs_guide.txt",
        "title": "Motor Insurance - Damage Photographs Standards Guide",
        "topic": "damage_photos",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Damage Photographs Standards Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=damage_photos, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide sets the technical and quality standards for photographic evidence submitted to support motor damage claims.

Section 2: When This Applies
Applies whenever damage photos must be taken and uploaded for accidents, crashes, glass breakage, floods, vandalism, or fire.

Section 3: Mandatory Photographic Views
To ensure rapid assessment without request for re-takes, upload:
1. Overall View: 4 wide-angle photos showing all four corners of the vehicle (front-left, front-right, rear-left, rear-right).
2. Number Plate View: Clear photo showing the full vehicle with the registration number plate clearly readable.
3. Specific Damage Shots: Medium-range and close-up photos showing dent depth, cracked panels, or displaced components.
4. Odometer Reading: Photo of the dashboard showing mileage and warning lights.
5. Vin Plate / Stamping: Photo of the chassis number plate inside the door jamb or engine bay.

Section 4: Technical and Lighting Quality
- Clear lighting: Take pictures during daylight or in well-lit garage conditions; avoid heavy shadows and flash glare on paint.
- No filters or edits: Photographs must be authentic and unedited; filters, cropping of vital areas, or digital tampering will trigger fraud alerts.
- Image resolution: Minimum 1080p resolution; file formats JPG, JPEG, or PNG under 10MB each.

Section 5: Photographing Special Damages
- Glass: Place a sheet of paper behind cracked windscreens to emphasize crack lines.
- Flood: Photograph water tide lines on upholstery, carpets, and door panels.
- Underside: If safe, photograph punctured oil pans or damaged suspension linkages.

Section 6: Important Notes and Practical Guidance
- Take immediate scene photos: Taking photos before vehicles are towed or dismantled provides the strongest evidence of impact veracity.

Section 7: Limitations and Human Review
AI photo analysis helps detect repairable components, while authorized claims assessors review photos to confirm repair quotes.
"""
    },
    {
        "filename": "synthetic_repair_estimates_guide.txt",
        "title": "Motor Insurance - Repair Estimates and Workshop Quotations Guide",
        "topic": "repair_estimates",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Repair Estimates and Workshop Quotations Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=repair_estimates, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document provides guidelines for obtaining and submitting automotive repair estimates, garage quotations, and mechanic bills.

Section 2: When This Applies
Applies to all claims involving physical vehicle damage where repair work, replacement parts, or repainting is required.

Section 3: Mandatory Information in Repair Estimates
A valid repair estimate must be issued on official workshop letterhead and include:
- Workshop details: Garage business name, tax registration number, phone number, and physical address
- Vehicle particulars: Vehicle registration number, make, model, chassis number, and odometer mileage
- Itemized parts: Distinct list of replacement parts with individual unit prices (OEM vs aftermarket)
- Labor charges: Itemized labor costs for panel beating, mechanical repair, and electrical work
- Paint and refinishing: Separate line items for paint materials and refinishing labor
- Total quotation: Clear subtotal, applicable taxes (VAT/GST), and grand total estimate

Section 4: Authorized vs Independent Workshops
- Approved Partner Garages: Enjoy direct billing, priority inspection, and guaranteed workmanship without out-of-pocket cash requirements.
- Non-Partner / Customer-Selected Garages: Subject to insurer assessor pre-inspection; payout may be settled via reimbursement basis.

Section 5: Supplementary Estimates
If hidden internal damage is uncovered after dismantling, the workshop must submit a supplementary estimate before commencing additional repairs.

Section 6: Important Notes and Practical Guidance
- Do NOT begin repairs before authorization: Starting repair work before official approval may result in disallowed parts costs.
- Betterment / Depreciation: Depending on vehicle age, depreciation deductions may apply to wear-and-tear replacement parts.

Section 7: Limitations and Human Review
Professional insurance assessors and claims officers audit all estimate line items against standard labor times and market part rates.
"""
    },
    {
        "filename": "synthetic_claim_reporting_timelines.txt",
        "title": "Motor Insurance - Claim Reporting Timelines and Deadlines",
        "topic": "claim_timelines",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Claim Reporting Timelines and Deadlines
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=claim_timelines, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document sets out the regulatory and contractual time limits for notifying incidents and submitting motor claims.

Section 2: When This Applies
Relevant to customers asking:
- "how long do i have to report an accident"
- "claim reporting deadline"
- "can i report a claim after two weeks"
- "delayed reporting policy rules"

Section 3: Standard Reporting Timelines
- Immediate Notice (within 24 hours): Theft, vehicle fire, hit-and-run, and accidents involving bodily injury should be reported immediately.
- Standard Collision Reporting (within 48 to 72 hours): Routine vehicle collisions and parking damage should be reported within 2 to 3 days of occurrence.
- Document Submission Window (within 14 days): Initial claim notification should be followed by full supporting documents within 14 days.

Section 4: Consequences of Delayed Notification
Failure to report incidents promptly may result in:
- Inability to verify fresh impact damage or paint transfer
- Loss of CCTV or eyewitness evidence
- Mandatory referral of the claim to the special investigations unit
- Potential repudiation if delay prejudices the insurer's legal defense against third parties

Section 5: Excusable Delays and Exceptions
Delays in notification may be accepted upon presentation of valid corroborating proof:
- Medical emergency: Driver hospitalized or medically incapacitated (medical discharge certificate required)
- Remote location: Incident occurred in an area without communication access
- Unavoidable detention or overseas travel

Section 6: Important Notes and Practical Guidance
- Report first, assemble papers second: You can lodge an initial claim notice immediately and upload quotes/documents later.

Section 7: Limitations and Human Review
Claims officers evaluate the reasons for late notifications on a case-by-case basis before accepting delayed claims.
"""
    },
    {
        "filename": "synthetic_claim_submission_process.txt",
        "title": "Motor Insurance - Step-by-Step Claim Submission Process",
        "topic": "submission_process",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Step-by-Step Claim Submission Process
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=submission_process, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide outlines the end-to-end journey of filing a motor insurance claim from incident occurrence to claim settlement.

Section 2: When This Applies
Applies to any customer inquiring:
- "how do i submit my claim"
- "what is the process for lodging a claim"
- "step by step claim filing"
- "how does motor insurance claim work"

Section 3: Step-by-Step Workflow
1. Step 1: Initial Notification: Customer interacts with the intake agent or customer portal, providing incident type, date, and location.
2. Step 2: Information Retrieval & Guidance: The retrieval agent identifies required documents; guidance agent provides clear requirements.
3. Step 3: Document Upload: The policyholder uploads driving licence, registration, photos, estimate, and police report if required.
4. Step 4: Submission Validation: The customer presses "Submit Claim"; orchestrator confirms all mandatory documents are attached.
5. Step 5: Advisory Fraud Triage: Automated risk triage calculates advisory risk indicators (no automated decisions).
6. Step 6: Human Assignment: An administrator assigns the claim file to an authorized claims officer.
7. Step 7: Officer Review & Decision: The officer reviews evidence and decides (Approve, Reject, Request More Info, Escalate).
8. Step 8: Settlement & Repair: Repair authorization issued to garage or settlement payout transferred to policyholder.

Section 4: Online Portal Navigation
Customers can track claim progress, receive notifications, and upload additional documents directly via their dashboard.

Section 5: Common Submission Bottlenecks
- Submitting blurry photos that do not show the license plate
- Missing driving licence copy of the person who drove the vehicle
- Submitting an estimate without itemized labor and parts breakdown

Section 6: Important Notes and Practical Guidance
- Draft Status: Your claim remains in draft or awaiting_documents until you click "Submit Claim".
- Notification: You will receive in-app notifications whenever your claim advances to a new workflow stage.

Section 7: Limitations and Human Review
While automated systems guide intake and validation, all claim decisions are strictly made by human claims personnel.
"""
    },
    {
        "filename": "synthetic_claim_status_explanations.txt",
        "title": "Motor Insurance - Claim Status Tracking and Explanations",
        "topic": "claim_status",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Claim Status Tracking and Explanations
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=claim_status, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document defines every status code used in our motor claims platform so customers can track their claim's progress.

Section 2: When This Applies
Relevant when customers query:
- "check my claim status"
- "what does under human review mean"
- "what is happening with my claim"
- "why is my status awaiting documents"

Section 3: Detailed Status Definitions
- draft / intake: Initial incident details recorded; claim identifier generated.
- awaiting_clarification: Critical details missing (e.g. location or what happened); chatbot is awaiting customer clarification.
- awaiting_documents: Claim created; system is waiting for the customer to upload required documents.
- documents_submitted: Customer uploaded all required documents and pressed "Submit Claim".
- fraud_triage_complete: Advisory risk indicators generated; claim ready for officer review.
- awaiting_assignment: File queued in common review backlog waiting for admin assignment to a claims officer.
- under_human_review: Claims officer actively examining policy coverage, estimate, photos, and police records.
- approved: Claim authorized for repair or payout; repair approval letter released.
- rejected: Claim declined due to policy exclusion, lapsed coverage, or non-compliance (rejection reason supplied).
- escalated: File referred to senior manager or legal counsel for complex multi-party or high-value assessment.

Section 4: What Customers Should Do at Each Stage
- If awaiting_documents: Upload missing items promptly through the portal.
- If under_human_review: No action required; the assigned officer is evaluating your file.
- If approved: Contact the authorized garage to schedule repair commencement.

Section 5: Notification Updates
Whenever your claim status updates, an in-app notification appears in your notification bell with a direct link to your claim summary.

Section 6: Important Notes and Practical Guidance
- Time in Review: Standard claims in "under_human_review" are typically assessed within 2 to 3 business days.

Section 7: Limitations and Human Review
Claims officers maintain sole authority to transition claims into approved, rejected, or escalated states.
"""
    },
    {
        "filename": "synthetic_policy_coverage_basics.txt",
        "title": "Motor Insurance - Policy Coverage Basics and Plan Types",
        "topic": "coverage_basics",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Policy Coverage Basics and Plan Types
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=coverage_basics, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains the basic principles of motor insurance coverage, plan tiers, and scope of protection under our demo system.

Section 2: When This Applies
Relevant to customers asking:
- "what does my policy cover"
- "difference between comprehensive and third party"
- "can you explain my motor policy"
- "does my policy cover flood damage"

Section 3: Motor Insurance Plan Tiers
1. Comprehensive Cover:
   - Provides the highest protection: covers damage to your own vehicle (collision, rollover, accidental damage)
   - Covers fire, lightning, self-ignition, explosion, and theft of the vehicle
   - Covers third-party property damage and bodily injury liability
   - May include natural disaster extensions (flood, storm, landslide) and windscreen cover.
2. Third-Party Fire and Theft (TPFT):
   - Covers third-party liability
   - Covers loss of or damage to your vehicle caused by fire, explosion, theft, or attempted theft
   - Does NOT cover accidental collision damage to your own vehicle.
3. Third-Party Only (TPO):
   - Minimum statutory cover: covers legal liability for damage to third-party property and injury to third parties
   - Does NOT cover any damage or loss to your own vehicle.

Section 4: Key Policy Parameters
- Sum Insured: The maximum agreed value payable in the event of total loss or theft.
- Policy Period: The exact effective dates between start date and expiry date.
- Territorial Limits: Geographical jurisdiction where policy coverage applies.

Section 5: Optional Endorsements
- Windscreen / Glass cover extension
- Natural Perils (flood, storm, cyclone) rider
- Passenger legal liability cover
- Roadside assistance and towing package

Section 6: Important Notes and Practical Guidance
- General guidance does not guarantee that your specific policy covers an event; always verify active policy schedules.

Section 7: Limitations and Human Review
Claims officers verify active coverage dates, plan tier, and endorsements against policy repository records during claim review.
"""
    },
    {
        "filename": "synthetic_policy_exclusions_limitations.txt",
        "title": "Motor Insurance - General Policy Exclusions and Limitations",
        "topic": "exclusions",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - General Policy Exclusions and Limitations
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=exclusions, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document explains common situations, risks, and circumstances that are excluded from motor insurance coverage across standard policies.

Section 2: When This Applies
Relevant when policyholders inquire:
- "why would a claim be excluded"
- "common insurance exclusions"
- "what is not covered by motor insurance"
- "does insurance pay if driver was drunk"

Section 3: Standard Statutory and Contractual Exclusions
The following circumstances are strictly excluded from coverage:
1. Driving Under the Influence: Operating the vehicle while impaired by alcohol, drugs, or illegal substances.
2. Unlicensed Driving: Driving without a valid driving license, or by an individual disqualified from driving.
3. Unapproved Commercial Use: Using a vehicle registered and insured for private use as an unapproved taxi, ride-hailing vehicle, or commercial haulage.
4. Illegal Activities & Racing: Damage occurring during speed trials, street racing, or criminal activities.
5. Inactive Policy: Losses occurring outside the policy start and end dates, or while policy is lapsed for non-payment.
6. Deliberate / Staged Damage: Intentional damage caused or orchestrated by the policyholder or driver.
7. Wear, Tear, and Mechanical Failure: Gradual deterioration, rust, corrosion, mechanical breakdown, or electrical burnout not caused by an insured peril.
8. War, Nuclear, and Civil Commotion: Damage caused by acts of war, rebellion, or nuclear radiation.

Section 4: Geographical and Environmental Limitations
- Operating the vehicle outside national territorial boundaries without an overseas coverage extension is excluded.

Section 5: Consequential Loss
- Deprivation of use, loss of income, car rental expenses (unless a courtesy car rider was purchased), and hotel bills are excluded.

Section 6: Important Notes and Practical Guidance
- No Automatic Rejection: Automated systems must NEVER reject a claim based on suspected exclusions.
- Full Investigation: Potential exclusions require thorough verification and evidence before any denial is issued.

Section 7: Limitations and Human Review
Decisions to decline a claim based on policy exclusions can only be authorized by a licensed claims officer with written justification.
"""
    },
    {
        "filename": "synthetic_deductible_excess_guide.txt",
        "title": "Motor Insurance - Deductibles and Policy Excess Guide",
        "topic": "deductibles_excess",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Deductibles and Policy Excess Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=deductibles_excess, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document clarifies the concepts of policy excess, deductibles, customer contributions, and how they apply during claim settlement.

Section 2: When This Applies
Relevant to policyholder queries:
- "deductible/excess meaning"
- "what is policy excess"
- "what is deductible"
- "deductibles and excess explained"
- "how does a deductible work"
- "do i have to pay excess if accident was not my fault"
- "compulsory vs voluntary excess"

Section 3: What is Policy Excess / Deductible?
A policy excess (or deductible/excess) is the agreed first amount of any claim that the policyholder must pay out-of-pocket towards the cost of repairs. The terms deductible and excess carry the same meaning in motor claims. The insurer covers the remaining balance above the excess amount up to the sum insured.
For example: If approved repair costs equal $1,500 and your policy excess is $250, the insurer pays $1,250 and you contribute $250.

Section 4: Types of Policy Excess
1. Compulsory (Standard) Excess: The mandatory deductible fixed by the insurer according to vehicle model and policy terms.
2. Voluntary Excess: An additional amount chosen by the policyholder to reduce their annual insurance premium.
3. Young or Inexperienced Driver Excess: An additional deductible applied when the driver at the time of accident is under 25 years of age or has held a full driving licence for less than two years.
4. Glass Excess: A specialized, lower excess applicable strictly to windscreen or glass repair/replacement.

Section 5: When Excess May Be Waived or Recovered
- Non-Fault Collision: If the accident was 100% caused by an identified third party whose insurer admits full liability, your excess may be waived or recovered from the third-party insurer.
- No Excess Windscreen Repair: Resin repairs of small stone chips often carry a zero excess incentive to avoid full glass replacement.

Section 6: Important Notes and Practical Guidance
- Excess Payment Timing: Excess is either deducted directly from the cash settlement or paid to the repair garage upon vehicle collection.
- Below-Excess Claims: If total repair costs are less than your excess amount, filing a claim is uneconomical.

Section 7: Limitations and Human Review
Claims officers calculate and verify applicable excess amounts according to the specific policy schedule during final settlement approval.
"""
    },
    {
        "filename": "synthetic_post_submission_lifecycle.txt",
        "title": "Motor Insurance - Post-Submission Claim Lifecycle Guide",
        "topic": "post_submission_lifecycle",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Post-Submission Claim Lifecycle Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=post_submission_lifecycle, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains what happens behind the scenes after a customer presses the "Submit Claim" button in our digital claims portal.

Section 2: When This Applies
Relevant to customers asking:
- "what happens after i submit my claim"
- "what are the next steps after claim submission"
- "how long does review take after submitting papers"
- "claim lifecycle after filing"

Section 3: Behind-the-Scenes Processing Steps
1. Immediate Validation: System checks that all mandatory documents for the reported incident type are attached. Status becomes "documents_submitted".
2. Advisory Fraud Triage: Agent 3 evaluates objective risk factors (rule-based score, document consistency). All automated indicators are purely advisory. Status moves to "fraud_triage_complete".
3. Internal Reviewer Summary: Agent 4 synthesizes a confidential internal overview for the claims team highlighting facts, missing proof, and policy details. Status moves to "awaiting_assignment".
4. Allocation to Officer: An administrator assigns the file from the common review queue to an authorized claims officer. Status updates to "under_human_review".
5. Assessment & Inspection: The officer cross-examines photographs, garage estimates, and policy terms, and may dispatch an engineer for on-site inspection.
6. Authoritative Decision: The claims officer approves, rejects, requests more information, or escalates.

Section 4: What the Policyholder Receives
- Immediate confirmation: Confirmation of submission with claim reference (CLM-...).
- Progress updates: Live tracking on the "My Claims" dashboard.
- Decision notification: Immediate in-app notification when the claims officer submits a decision.

Section 5: Typical Processing Timelines
- Initial review: 24 to 48 business hours after document submission.
- Assessor inspection (if needed): 2 to 4 business days.
- Repair authorization: Released within 24 hours of claim approval.

Section 6: Important Notes and Practical Guidance
- Chat Unlocked: Submitting a claim does not lock your chat interface; you can continue asking questions or check status anytime.

Section 7: Limitations and Human Review
Our architecture strictly adheres to "AI Assists, Human Decides": no claim is ever automatically approved or denied without authorized human review.
"""
    },
    {
        "filename": "synthetic_human_review_process.txt",
        "title": "Motor Insurance - Human Review Process and Officer Authority",
        "topic": "human_review",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Human Review Process and Officer Authority
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=human_review, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document describes the governance, principles, and procedures governing human claims officer adjudication in our motor insurance system.

Section 2: When This Applies
Relevant when understanding who decides claims and how decisions are made:
- "who makes the decision on my claim"
- "does an AI decide my claim"
- "role of claims officer"
- "how are claims evaluated"

Section 3: Authoritative Human Governance
- AI Assists, Human Decides: All AI components (Agent 1 Intake, Agent 2 Retrieval, Agent 3 Fraud Triage, Agent 4 Guidance) are advisory. They catalog evidence, retrieve rules, and summarize facts.
- Authoritative Mandate: Only a licensed, authorized human claims officer or administrator holds the legal authority to approve claims, reject claims, request more information, or escalate files.

Section 4: Claims Officer Review Checklist
When reviewing an assigned claim, the officer evaluates:
1. Policy Coverage: Verifies active policy dates, premium standing, plan tier, and covered perils.
2. Incident Veracity: Checks that the reported accident narrative aligns with the photographic damage patterns.
3. Repair Quotation Audit: Reviews itemized repair estimates against standardized labor rates and parts pricing.
4. Legal & Regulatory Compliance: Verifies driver's licence validity, vehicle registration, and police reports where applicable.
5. Advisory Risk Indicators: Evaluates Agent 3 fraud triage indicators with human judgment.

Section 5: Decision Options
- Approve: Approves the repair quote or authorizes settlement disbursement.
- Reject: Rejects the claim with a mandatory written justification citing applicable policy terms.
- Request More Information: Pauses evaluation and requests specific missing documents or clarifications from customer.
- Escalate: Refers complex, high-value, or legally disputed claims to a senior manager or legal counsel.

Section 6: Important Notes and Practical Guidance
- Confidentiality: Internal risk notes and fraud indicators remain confidential to staff and are never disclosed to customers.

Section 7: Limitations and Human Review
Human review ensures fairness, transparency, and accountability across every insurance decision.
"""
    },
    {
        "filename": "synthetic_request_for_more_information.txt",
        "title": "Motor Insurance - Request for More Information Guide",
        "topic": "request_more_info",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Request for More Information Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=request_more_info, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains the procedure when a claims officer issues a "Request for More Information" (RFI) during claim adjudication.

Section 2: When This Applies
Relevant to policyholders asking:
- "why was more information requested"
- "what to do when insurer asks for more documents"
- "claim status changed to awaiting documents after review"
- "how to provide requested information"

Section 3: Common Reasons for Information Requests
A claims officer may request additional details when:
- Submitted damage photographs are blurry, dark, or do not display the vehicle registration plate
- Repair estimate lacks itemized parts numbers, labor hours, or paint breakdown
- Driver's license copy is cropped, expired, or missing the reverse side
- Police report extract is pending or requires a certified copy from the police station
- Third-party contact details or eyewitness statements are required to verify fault
- Mechanical inspection report is needed for suspected engine water immersion or gearbox failure

Section 4: What Happens to Claim Workflow
- Status Transition: Workflow status transitions back to "awaiting_documents".
- Customer Notification: An in-app notification and email are dispatched specifying the exact documents or explanations requested.
- Preserved History: All previously uploaded documents remain safely stored; only newly requested items need to be submitted.

Section 5: How the Customer Should Respond
1. Open Claim Details: Navigate to "My Claims" and click on the claim reference.
2. Review Notes: Read the officer's specific notes detailing the requested items.
3. Upload New Files: Use the document upload section to attach the required files.
4. Resubmit: Click "Submit Claim" to return the updated file to the claims officer.

Section 6: Important Notes and Practical Guidance
- Response Deadline: Submit requested information within 14 business days to prevent administrative claim suspension.

Section 7: Limitations and Human Review
Information requests are initiated directly by human claims officers to give customers full opportunity to substantiate their claims before a final decision.
"""
    },
    {
        "filename": "synthetic_claim_rejection_explanation.txt",
        "title": "Motor Insurance - Claim Rejection Explanation and Appeals Guide",
        "topic": "claim_rejection",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Claim Rejection Explanation and Appeals Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=claim_rejection, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This document outlines the formal process, requirements, and rights associated with claim repudiation or rejection under our motor insurance platform.

Section 2: When This Applies
Relevant when customers inquire:
- "why was my claim rejected"
- "claim declined explanation"
- "can i appeal a rejected claim"
- "insurance refusal reasons"

Section 3: Mandatory Rejection Standards
- No Automated Rejection: Our system strictly forbids automated AI rejections. Every rejection requires explicit human claims officer review.
- Mandatory Written Justification: Claims officers cannot reject a claim without providing a non-empty, detailed, customer-safe explanation. Empty or whitespace-only reasons are programmatically blocked with HTTP 409 Conflict.
- Specific Policy Reference: The rejection rationale must identify the specific policy exclusion, condition, or factual ground for denial.

Section 4: Common Legitimate Grounds for Rejection
1. Coverage Inactive: The reported incident occurred prior to the policy inception date or after policy expiration.
2. Uncovered Peril: The claimed peril is not covered under the plan tier (e.g., claiming own-damage collision under a Third-Party Only policy).
3. Contractual Exclusion: Driver was intoxicated, unlicensed, or vehicle was used for unapproved commercial racing/hire.
4. Material Misrepresentation: Intentional falsification of accident date, circumstances, or staged damage.
5. Wear and Tear: Damage is purely mechanical breakdown or age-related corrosion rather than an accidental impact.

Section 5: Customer Appeals and Review Options
If you believe your claim was rejected in error:
1. Internal Dispute Resolution: You may submit a written appeal providing new evidence (e.g. additional photos, witness statements, or police findings).
2. Escalation Request: Request supervisory re-evaluation by an escalation claims manager.
3. Insurance Ombudsman: Independent external arbitration options are available under financial regulatory oversight.

Section 6: Important Notes and Practical Guidance
- Rejection Notices: Written rejection details are visible on your claim details screen and preserved in your audit history.

Section 7: Limitations and Human Review
Claims officers are held to strict ethical and procedural standards when issuing rejection decisions.
"""
    },
    {
        "filename": "synthetic_claim_escalation_review.txt",
        "title": "Motor Insurance - Claim Escalation and Supervisory Review Guide",
        "topic": "claim_escalation",
        "incident_type": "general",
        "version": "1.0",
        "content": """# Motor Insurance - Claim Escalation and Supervisory Review Guide
[DEMO / SYNTHETIC DOCUMENT FOR TESTING AND DEMONSTRATION PURPOSES ONLY - NOT AN OFFICIAL INSURER POLICY]
[METADATA: topic=claim_escalation, incident_type=general, synthetic=true, version=1.0]

Section 1: Scope and Application
This guide explains the escalation pathway when a claim requires senior management evaluation, multi-party dispute resolution, or legal review.

Section 2: When This Applies
Applies when a claim status is set to "escalated", or when a policyholder requests senior supervisory re-evaluation. Relevant queries:
- "what does escalated status mean"
- "why is my claim escalated"
- "second review of motor claim"
- "supervisory claim assessment"

Section 3: Why Claims Are Escalated
A claims officer escalates a claim file when:
- High Value / Total Loss: Repair estimates exceed significant monetary thresholds or approach constructive total loss limits.
- Complex Multi-Party Collisions: Three or more vehicles involved with contested liability and cross-claims.
- Legal Action / Summons: Court summons, third-party attorney letters, or statutory notices received.
- Fraud Investigation: Special Investigations Unit (SIU) forensic audit recommended due to conflicting damage patterns.
- Policy Ambiguity: Interpretation of non-standard endorsements or complex policy exclusions requires legal counsel opinion.

Section 4: Escalation Review Workflow
1. Escalation Note: The reviewing claims officer attaches detailed notes specifying the reason for escalation.
2. Workflow Status: Status updates to "escalated"; policyholder receives notification that additional specialist review is underway.
3. Senior Panel Review: A senior claims manager, technical loss engineer, or legal counsel examines the complete claim docket.
4. Resolution: The escalation panel issues a binding determination (Approve with adjusted settlement, Request specific evidence, or Confirm Repudiation).

Section 5: Escalation Timeframes
Due to multi-party or technical investigations, escalated claims typically conclude within 5 to 10 business days. Regular status updates appear in the customer portal.

Section 6: Important Notes and Practical Guidance
- Cooperation: If the escalation panel requests forensic vehicle examination or recorded statements, prompt cooperation speeds up resolution.

Section 7: Limitations and Human Review
Escalation ensures senior human oversight and equitable resolution of complex and contentious claims.
"""
    }
]


def generate() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for doc in DOCUMENTS:
        file_path = TARGET_DIR / doc["filename"]
        raw = doc["content"].strip()
        lines = raw.splitlines()
        if lines and lines[0].startswith("# "):
            lines[0] = lines[0][2:]
        text = "\n".join(lines)
        file_path.write_text(text + "\n", encoding="utf-8")
        created += 1
        print(f"Created: {doc['filename']}")
    print(f"\nSuccessfully generated {created} synthetic policy documents in {TARGET_DIR}")


if __name__ == "__main__":
    generate()
