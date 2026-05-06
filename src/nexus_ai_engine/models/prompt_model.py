"""
Prompt Configuration Models

Pydantic models for configurable AI prompts used in call analysis.
Supports call summary and product details extraction prompts.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PromptType(str, Enum):
    """Types of configurable prompts"""
    CALL_SUMMARY = "call_summary"
    PRODUCT_DETAILS = "product_details"
    SF_CREATE_LEAD_PAYLOAD = "sf_create_lead_payload"
    SF_DEAL_QUERY = "sf_deal_query"
    SF_PRICING_QUERY = "sf_pricing_query"
    SF_RESPONSE_COMPILE = "sf_response_compile"
    # TMF/BSSMagic-specific prompts for Step 6 CRM actions
    TMF_LEAD_PAYLOAD = "tmf_lead_payload"
    TMF_CONTENT_VERSION_PAYLOAD = "tmf_content_version_payload"
    TMF_PRODUCT_QUERY = "tmf_product_query"
    TMF_PRICING_QUERY = "tmf_pricing_query"
    TMF_RECORD_TYPE_QUERY = "tmf_record_type_query"
    TMF_SFDC_ACTIONS_COMPILE = "tmf_sfdc_actions_compile"


class PromptEntry(BaseModel):
    """Individual prompt configuration"""
    id: str = Field(..., description="Unique prompt identifier (matches PromptType)")
    name: str = Field(..., description="Human-readable prompt name")
    description: str = Field(..., description="Description of what this prompt does")
    content: str = Field(..., description="The actual prompt text with placeholders")
    max_length: int = Field(10000, description="Maximum allowed length for prompt content")
    placeholders: List[str] = Field(default_factory=list, description="List of placeholder variables in the prompt")
    is_default: bool = Field(True, description="Whether this is the default (not customized)")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    updated_by: Optional[str] = Field(None, description="User who last updated this prompt")


class PromptAuditEntry(BaseModel):
    """Audit log entry for prompt changes"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(..., description="Action performed (UPDATE, RESET)")
    user_id: str = Field(..., description="User who performed the action")
    prompt_id: str = Field(..., description="Prompt that was modified")
    previous_content: Optional[str] = Field(None, description="Previous prompt content (truncated)")
    new_content: Optional[str] = Field(None, description="New prompt content (truncated)")


class PromptMetadata(BaseModel):
    """Metadata for prompt configuration"""
    version: str = Field("1.0.0", description="Configuration version")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    environment: str = Field("development", description="Environment name")


class PromptConfig(BaseModel):
    """Complete prompt configuration"""
    metadata: PromptMetadata = Field(default_factory=PromptMetadata)
    prompts: List[PromptEntry] = Field(default_factory=list)
    audit_log: List[PromptAuditEntry] = Field(default_factory=list)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z" if v else None
        }


# Request/Response Models for API

class UpdatePromptRequest(BaseModel):
    """Request to update a prompt"""
    content: str = Field(..., description="New prompt content", min_length=10, max_length=10000)


class UpdatePromptResponse(BaseModel):
    """Response after updating a prompt"""
    success: bool
    message: str
    prompt_id: str
    updated_at: datetime


class PromptListResponse(BaseModel):
    """API response for prompts list"""
    success: bool = True
    data: List[PromptEntry]
    count: int


class PromptResetResponse(BaseModel):
    """API response for reset operation"""
    success: bool
    message: str
    reset_prompts: List[str]


# Default Prompts

DEFAULT_CALL_SUMMARY_PROMPT = """Analyze the following sales call transcript and generate a concise one-paragraph summary.

## FORMAT REQUIREMENTS:
Generate a single paragraph in this exact format:
"Customer [Name] from [Company] inquired about [Products/Services]. Email: [email or N/A]. Phone: [phone or N/A]. BRN: [BRN if mentioned, or 'generated: XXX' if not provided]. Requirements: [key requirements mentioned]. Contract: [contract details if discussed]. Customer segment: [SME/Enterprise/Consumer]."

## EXTRACTION RULES:
1. Customer Name: Extract from how the agent addresses the customer or self-introduction
2. Company: Extract company/organization name mentioned
3. Products/Services: List all products discussed (e.g., "Business Internet 300 Mbps, SmartUC")
4. Email: Extract if mentioned, otherwise "N/A"
5. Phone: Extract if mentioned, otherwise "N/A"  
6. BRN/UEN: Business Registration Number (also called UEN - Unique Entity Number) — follow these rules carefully:
   - Singapore BRN/UEN format: 9-10 characters, typically NNNNNNNNX or YYYYNNNNNX (N=digit, X=letter)
   - If customer spells characters using NATO/phonetic alphabet, convert: Alpha=A, Bravo=B, Charlie=C, Delta=D, Echo=E, Foxtrot=F, Golf=G, Hotel=H, India=I, Juliet=J, Kilo=K, Lima=L, Mike=M, November=N, Oscar=O, Papa=P, Quebec=Q, Romeo=R, Sierra=S, Tango=T, Uniform=U, Victor=V, Whiskey=W, X-ray=X, Yankee=Y, Zulu=Z
   - If customer spells digits one-by-one (e.g. "one nine two three four"), convert each word to its digit
   - If customer uses country names as letters (e.g. "N for November"), extract the letter
   - CRITICAL: The last character of a Singapore BRN/UEN is almost always a LETTER. If the customer says a NATO word (Echo, November, Delta, etc.) as the final part, it IS the trailing letter — NEVER drop it
   - Capture ALL characters without skipping — do NOT truncate or drop middle digits or trailing letters
   - Example: "one nine nine one zero one six six nine Echo" = "199101669E"
   - If not mentioned, write "not provided"
7. Requirements: Key technical requirements (bandwidth, IPs, contract length, etc.)
8. Contract: Contract terms discussed (duration, pricing, terms)
9. Segment: Determine if SME, Enterprise, or Consumer based on context

## TRANSCRIPT:
{transcript_text}

## CALL METADATA:
- Call ID: {call_id}
- Agent: {agent_name}
- Customer Company: {customer_company}
- Call Date: {call_date}

Return ONLY the summary paragraph. No JSON, no markdown formatting, no additional text."""


DEFAULT_PRODUCT_DETAILS_PROMPT = """Extract product details from the following call transcript. Return valid JSON only.

## TRANSCRIPT:
{transcript_text}

## CALL METADATA:
- Call ID: {call_id}
- Customer Company: {customer_company}
- Call Date: {call_date}

## EXTRACTION RULES:
1. Identify ALL products/services mentioned in the call
2. For each product, extract:
   - product_name: Exact product name as mentioned (e.g., "Business Internet Light Dedicated 300 Mbps")
   - product_type: Category (e.g., "Internet Service", "Voice Service", "Mobile Service", "TV Service")
   - bandwidth: Network speed if applicable (e.g., "300 Mbps", "1 Gbps"), null if not applicable
   - contract_length: Contract duration as string (e.g., "24 months", "36 months"). Default "24 months" if not discussed.
   - contract_term_months: Contract duration as a number in months (e.g., 24, 36, 12). Default 24 if not discussed.
   - estimated_monthly_cost: Monthly cost in SGD if mentioned, null if not discussed
   - quantity: Number of connections, lines, licenses, or units requested by customer. Default 1 if not discussed. If customer says "6 lines" or "6 connections", set to 6.
   - features: Array of features/benefits mentioned
   - customer_interest: Base ONLY on explicit customer statements — "high" if customer said yes/agreed/showed enthusiasm, "medium" if customer asked questions but did not commit, "low" if customer expressed hesitation or said no

3. Extract BRN/UEN (Business Registration Number, also called UEN or Unique Entity Number) if mentioned, empty string if not. Follow these rules:
   - Singapore BRN/UEN format: 9-10 characters, typically NNNNNNNNX or YYYYNNNNNX (N=digit, X=letter)
   - If customer spells characters using NATO/phonetic alphabet, convert: Alpha=A, Bravo=B, Charlie=C, Delta=D, Echo=E, Foxtrot=F, Golf=G, Hotel=H, India=I, Juliet=J, Kilo=K, Lima=L, Mike=M, November=N, Oscar=O, Papa=P, Quebec=Q, Romeo=R, Sierra=S, Tango=T, Uniform=U, Victor=V, Whiskey=W, X-ray=X, Yankee=Y, Zulu=Z
   - If customer spells digits one-by-one (e.g. "one nine two three four"), convert each word to its digit
   - If customer uses country names as letters (e.g. "N for November"), extract the letter
   - CRITICAL: The last character of a Singapore BRN/UEN is almost always a LETTER. If the customer says a NATO word (Echo, November, Delta, etc.) as the final part, it IS the trailing letter — NEVER drop it
   - Capture ALL characters without skipping — do NOT truncate or drop middle digits or trailing letters
   - Example: "one nine nine one zero one six six nine Echo" = "199101669E"

## REQUIRED OUTPUT FORMAT:
Return ONLY this JSON structure with no additional text:
{{
  "call_id": "{call_id}",
  "customer_company": "{customer_company}",
  "call_date": "{call_date}",
  "BRN": "",
  "products": [
    {{
      "product_name": "string",
      "product_type": "string",
      "bandwidth": "string or null",
      "contract_length": "string",
      "contract_term_months": 24,
      "estimated_monthly_cost": null,
      "quantity": 1,
      "features": ["feature1", "feature2"],
      "customer_interest": "high|medium|low"
    }}
  ]
}}

If no products are discussed, return an empty products array.
Return ONLY valid JSON. No markdown, no code blocks, no explanations."""


DEFAULT_SF_CREATE_LEAD_PAYLOAD_PROMPT = """You are a Salesforce Lead data extraction assistant. Given call summary and product details from a sales call, generate a valid JSON payload for creating a Salesforce Lead.

## CONNECTOR TYPE:
{connector_type}

## CALL SUMMARY:
{call_summary}

## PRODUCT DETAILS:
{product_details}

## EXTRACTION RULES:
1. Extract customer contact information from the call summary
2. Parse contact name into firstName/FirstName and lastName/LastName:
   - If name has multiple parts, last part is lastName, rest is firstName
   - If only one name, treat as lastName

3. For AXWAY connector, map service types to serviceTypeEnquired values:
   - Internet → "Enterprise Internet - New"
   - Broadband → "Business Broadband (NGNBN) - New"
   - Mobile → "Mobile - New"
   - Voice → "Enterprise Voice - New"
   - SmartUC → "StarHub O.N.E Phone - New"
   - Cloud → "Cloud Computing - New"
   - SIP → "SIP Trucking - New"
   - Not specified → "Did Not Specify"

4. For SFDC_DIRECT connector, use LeadSource values:
   - "Web", "Phone Inquiry", "Partner Referral", "Purchased List", "Other"

## OUTPUT FORMAT BASED ON CONNECTOR:

### If connector_type is "axway":
Generate Axway API format (camelCase fields):
{{
  "lastName": "string (required)",
  "firstName": "string (optional)",
  "company": "string (required)",
  "email": "string (required - use placeholder@email.com if not found)",
  "leadSource": "1800 Sales Hotline",
  "serviceTypeEnquired": "string (required - mapped service type)",
  "productEnquired": "string (optional - specific products)",
  "leadStatus": "Open Lead",
  "mobilePhone": "string (optional)",
  "leadCurrency": "SGD"
}}

### If connector_type is "direct" or "sfdc":
Generate Salesforce Direct API format (PascalCase fields):
{{
  "LastName": "string (required)",
  "FirstName": "string (optional)",
  "Company": "string (required)",
  "Email": "string (required - use placeholder@email.com if not found)",
  "Phone": "string (optional)",
  "LeadSource": "Phone Inquiry",
  "Description": "Service Inquiry: [service_type]. Products: [products_discussed]. BRN: [brn_if_available].",
  "Status": "Open - Not Contacted"
}}

Return ONLY valid JSON matching the connector_type format. No markdown, no code blocks, no explanations."""


DEFAULT_SF_DEAL_QUERY_PROMPT = """You are a SOQL query generator for Salesforce StarHub CPQ. Given product details from a sales call, generate a SOQL query to find matching products.

## PRODUCT DETAILS:
{product_details}

## TARGET OBJECT: cspmb__Price_Item__c (Commercial Products)
Fields to select: Id, Name, cspmb__Price_Item_Code__c

## QUERY GENERATION RULES:

1. Extract product names/types from the input (e.g., "Business Internet", "SmartUC", "Enterprise Voice")

2. Generate a query to find matching cspmb__Price_Item__c records:
   - Use Name LIKE '%keyword%' for fuzzy matching
   - Include multiple OR conditions for different product names
   - Always add LIMIT 10

3. Map common service types to product keywords:
   - Internet → "Internet", "Dedicated", "Broadband"
   - Voice → "Voice", "SmartUC", "SIP", "Phone"
   - Mobile → "Mobile", "Cellular"
   - Broadband → "Broadband", "NGNBN", "Fibre"

## OUTPUT FORMAT:
Return ONLY the SOQL query string. No markdown, no code blocks, no explanations.

## EXAMPLES:

SELECT Id, Name, cspmb__Price_Item_Code__c FROM cspmb__Price_Item__c WHERE (Name LIKE '%Internet%' OR Name LIKE '%Voice%') LIMIT 10

SELECT Id, Name, cspmb__Price_Item_Code__c FROM cspmb__Price_Item__c WHERE Name LIKE '%Business Internet 300%' LIMIT 5"""


DEFAULT_SF_PRICING_QUERY_PROMPT = """You are a SOQL query generator for Salesforce StarHub CPQ. Given product IDs from Salesforce, generate a SOQL query to fetch their pricing information.

## PRODUCT IDS FOUND:
{product_ids}

## PRODUCT DETAILS:
{product_names}

## TARGET OBJECT: cspmb__Price_Item_Pricing_Rule_Association__c
Fields to select: Id, cspmb__price_item__c, cspmb__one_off_adjustment__c, cspmb__recurring_adjustment__c

## QUERY GENERATION RULES:

1. Use the product IDs provided to query pricing rules
2. Filter for 'Initial Price' type adjustments
3. Filter for SGD currency
4. Limit results appropriately

## OUTPUT FORMAT:
Return ONLY the SOQL query string. No markdown, no code blocks, no explanations.

## EXAMPLE:

For product IDs ['a0B123', 'a0B456', 'a0B789']:
SELECT Id, cspmb__price_item__c, cspmb__price_item__r.Name, cspmb__one_off_adjustment__c, cspmb__recurring_adjustment__c FROM cspmb__Price_Item_Pricing_Rule_Association__c WHERE cspmb__price_item__c IN ('a0B123', 'a0B456', 'a0B789') AND (cspmb__recurring_adjustment_type__c = 'Initial Price' OR cspmb__one_off_adjustment_type__c = 'Initial Price') AND currencyISOCode = 'SGD' LIMIT 50"""


DEFAULT_SF_RESPONSE_COMPILE_PROMPT = """You are a Salesforce response processor. Given API responses from Salesforce/Axway operations, compile them into a structured sfdc_action.json format.

## OPERATION TYPE:
{operation_type}

## API RESPONSE:
{api_response}

## TRANSCRIPT ANALYSIS (context):
{transcript_analysis}

## TASK ID:
{task_id}

## COMPILATION RULES:

### For Lead Creation (operation_type: "create_lead"):
1. Extract lead_id from response (look for "id", "leadId", "lead_id", or "Id" fields)
2. Extract success status (response status code 200/201 or "success": true)
3. Build action entry with type "lead", action "created"
4. Include details: company_name, contact_name, email, phone, brn, service_inquiry
5. Format message as: "Lead created: [contact_name] - [company_name] - [service_inquiry]"

### For Lead Conversion (operation_type: "convert_lead"):
1. Extract opportunity_id and account_id from response
2. Build action entry with type "lead", action "updated"
3. Include status "converted" in details

### For Opportunity Creation (operation_type: "create_opportunity"):
1. Extract opportunity_id from response
2. Build action entry with type "opportunity", action "created"
3. Include account_id and opportunity details

### For Query/Retrieve (operation_type: "retrieve_query"):
1. Extract records from response
2. Build action entry with type "query", action "retrieved"
3. Include record count and summary in details

## REQUIRED OUTPUT FORMAT:
Generate a valid JSON object matching this structure:
{{
  "task_id": "{task_id}",
  "executed_at": "[current ISO timestamp]",
  "actions": [
    {{
      "type": "lead|opportunity|query",
      "action": "created|updated|retrieved",
      "record_id": "[extracted record ID or empty string]",
      "details": {{
        "company_name": "[from transcript_analysis]",
        "contact_name": "[from transcript_analysis]",
        "email": "[from response or transcript_analysis]",
        "phone": "[from response or transcript_analysis]",
        "brn": "[from transcript_analysis if available]",
        "service_inquiry": "[from transcript_analysis]",
        "message": "[descriptive message about the action]"
      }}
    }}
  ],
  "success": true|false,
  "errors": []
}}

## ERROR HANDLING:
- If API response indicates failure, set success to false
- Add error message from response to errors array
- Still populate actions array with available information

Return ONLY valid JSON. No markdown, no code blocks, no explanations."""


# ═══════════════════════════════════════════════════════════════════════════════
# TMF / BSSMagic Prompt Templates
# These generate payloads for the BSSMagic runtime TMF REST API (port 9000)
# which maps to PostgreSQL FDW views backed by Salesforce via Axway.
# Field names must match the FDW view column names exactly.
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_TMF_LEAD_PAYLOAD_PROMPT = """You are a TMF SalesLead data extraction assistant. Given a call summary and product details from a sales call, generate a valid JSON payload for creating a Lead via the BSSMagic TMF API.

## RECORD TYPE ID:
{record_type_id}

## OWNER ID:
{owner_id}

## CALL SUMMARY:
{call_summary}

## PRODUCT DETAILS:
{product_details}

## FIELD MAPPING (BSSMagic FDW view columns):
The payload MUST use these exact field names (they map to Salesforce Lead fields via FDW):
- familyName → LastName (MANDATORY, max 80 chars)
- givenName → FirstName (optional, max 80 chars)
- name → Company (MANDATORY, max 255 chars)
- email → Email (MANDATORY, use placeholder@starhub.com if not found)
- source → LeadSource (MANDATORY, pick from LEAD SOURCE VALUES below)
- serviceTypeEnquired → Type_of_Services_Enquired__c (MANDATORY, pick from SERVICE TYPE VALUES below)
- leadCurrency → CurrencyIsoCode (MANDATORY, use "SGD")
- ownerId → OwnerId (MANDATORY, use the owner_id provided above)
- mobilePhone → MobilePhone (optional)
- mobileType → CPQ_Mobile_Number_Type__c (optional: "Local" or "Foreign")
- status → Status (use "Open Lead")
- productEnquired → Products_Enquired__c (optional, pick from PRODUCT ENQUIRED VALUES below)
- customerType → Customer_Type__c (optional: "New", "Existing", etc.)
- leadRemarks → Lead_Remarks__c (optional, brief call context)
- brn → Business_Registration_Number_BRN__c (optional)
- recordTypeId → RecordTypeId (use the record_type_id provided above)
- salutation → Salutation (optional: "Mr.", "Mrs.", "Ms.", "Dr.")

## SERVICE TYPE ENQUIRED VALUES (RESTRICTED PICKLIST - use ONLY one of these exact values):
"ADSL Bundle with MaxMobile - New", "ADSL Bundle with MaxMobile - Recontract", "ADSL Bundle with MaxMobile - Upgrade",
"ADSL Bundle with Mobile - New", "ADSL Bundle with Mobile - Recontract", "ADSL Bundle with Mobile - Upgrade",
"Arcstar - New", "Arcstar - Recontract", "Arcstar - Upgrade", "AutoDesk",
"Backhaul - New", "Backhaul - Recontract", "Backhaul - Upgrade",
"BlackBerry - New", "BlackBerry - Recontract", "BlackBerry - Upgrade",
"Business Broadband (ADSL) - New", "Business Broadband (ADSL) - Recontract", "Business Broadband (ADSL) - Upgrade",
"Business Broadband (EntWeb) - New", "Business Broadband (EntWeb) - Recontract", "Business Broadband (EntWeb) - Upgrade",
"Business Broadband (NGNBN) - New", "Business Broadband (NGNBN) - Recontract", "Business Broadband (NGNBN) - Upgrade",
"Business Solution Service - New", "Business Solution Service - Recontract", "Business Solution Service - Upgrade",
"CableTV - New", "CableTV - Recontract", "CableTV - Upgrade",
"Cloud Computing - New", "Cloud Computing - Recontract", "Cloud Computing - Upgrade",
"Did Not Specify", "Digital Transformation Solutions",
"DLC - New", "DLC - Recontract", "DLC - Upgrade",
"DTTV - New", "DTTV - Recontract", "DTTV - Upgrade",
"EHRM - New", "EHRM - Recontract", "EHRM - Upgrade",
"Enterprise Internet - New", "Enterprise Internet - Recontract", "Enterprise Internet - Upgrade",
"Enterprise Voice - New", "Enterprise Voice - Recontract", "Enterprise Voice - Upgrade",
"Enterprise Web - New", "Enterprise Web - Recontract", "Enterprise Web - Upgrade",
"Facilities Management - New", "Facilities Management - Recontract", "Facilities Management - Upgrade",
"Global Access New", "Global Access Renewal", "Global Access Upgrade",
"Global VPN - New", "Global VPN - Recontract", "Global VPN - Upgrade",
"IaaS", "IDD",
"IEPL - New", "IEPL - Recontract", "IEPL - Upgrade",
"International Call Services - New", "International Call Services - Recontract", "International Call Services - Upgrade",
"Internet Leased Line - New", "Internet Leased Line - Recontract", "Internet Leased Line - Upgrade",
"Intl Managed Services - New", "Intl Managed Services - Recontract", "Intl Managed Services - Upgrade",
"IPLC - New", "IPLC - Recontract", "IPLC - Upgrade",
"IPTV - New", "IPTV - Upgrade",
"ISDN2 - New", "ISDN2 - Recontract", "ISDN2 - Upgrade",
"ISDN30 - New", "ISDN30 - Recontract", "ISDN30 - Upgrade",
"Managed CPE Service - New", "Managed CPE Service - Recontract", "Managed CPE Service - Upgrade",
"Managed Multi Link Service - New", "Managed Multi Link Service - Recontract", "Managed Multi Link Service - Upgrade",
"MaxMobile - New", "MaxMobile - Recontract", "MaxMobile - Upgrade",
"MMS - New", "MMS - Recontract", "MMS - Upgrade",
"Mobile - New", "Mobile - Recontract", "Mobile Suite", "Mobile - Upgrade",
"MYOB - New", "MYOB - Recontract", "MYOB - Upgrade",
"NGNBN Bundle with MaxMobile - New", "NGNBN Bundle with MaxMobile - Recontract", "NGNBN Bundle with MaxMobile - Upgrade",
"NGNBN Bundle with Mobile - New", "NGNBN Bundle with Mobile - Recontract", "NGNBN Bundle with Mobile - Upgrade",
"OE - New", "OE - Recontract", "OE - Upgrade",
"OIAB - New", "OIAB - Recontract", "OIAB - Upgrade",
"PowerOffice - New", "PowerOffice - Recontract", "PowerOffice - Upgrade",
"PSTS - New", "PSTS - Recontract", "PSTS - Upgrade",
"SIP Trucking - New", "Smart Office Suite",
"StarHub Email Security - New", "StarHub Email Security - Recontract", "StarHub Email Security - Upgrade",
"StarHub EnterpriseMessaging - New", "StarHub EnterpriseMessaging - Recontract", "StarHub EnterpriseMessaging - Upgrade",
"StarHub IP Exchange - SIX - New", "StarHub IP Exchange - SIX - Recontract", "StarHub IP Exchange - SIX - Upgrade",
"StarHub O.N.E Phone - New", "StarHub O.N.E Phone - Recontract", "StarHub O.N.E Phone - Upgrade",
"StarHub POS - New", "StarHub POS - Recontract", "StarHub POS - Upgrade",
"StarHub Web Security - New", "StarHub Web Security - Recontract", "StarHub Web Security - Upgrade",
"Switch Ethernet (SWE) - New", "Switch Ethernet (SWE) - Recontract", "Switch Ethernet (SWE) - Upgrade",
"SWS - New", "SWS - Recontract", "SWS - Upgrade",
"SAAS - Integrated Smart Retail"

## COMMON SERVICE TYPE MAPPING (use as guide, always pick the closest match from above):
- Internet/Dedicated Internet → "Enterprise Internet - New"
- Business Broadband/NGNBN/Fibre → "Business Broadband (NGNBN) - New"
- Mobile/Cellular → "Mobile - New"
- Voice/SmartUC → "Enterprise Voice - New" or "StarHub O.N.E Phone - New"
- SIP/SIP Trunk → "SIP Trucking - New"
- Cloud/IaaS → "Cloud Computing - New"
- SD-WAN/VPN → "Global VPN - New"
- Email Security → "StarHub Email Security - New"
- Web Security → "StarHub Web Security - New"
- Messaging → "StarHub EnterpriseMessaging - New"
- Unknown/Not specified → "Did Not Specify"

## LEAD SOURCE VALUES (RESTRICTED - use ONLY one of these exact values):
"(For CP USE ONLY) CP (Cold-calling)", "(For CP USE ONLY) CP Inbound",
"1631 Biz Helpdesk", "1800 Sales Hotline", "Biz Mailbox",
"Call out activity for MA Team", "Content Download", "CS Technical Helpdesk",
"EBG Internal Referral", "EBG Outbound Rep", "EBG Outbound Rep (Recon)",
"IS Call Out Activity", "ISR Direct Contact",
"Marketing (Database)", "Marketing (Direct Mailer)", "Marketing (Door-to-Door)",
"Marketing (Event)", "Marketing (Telemarketing)",
"Recontracting Exercise", "Recontracting Exercise (Fixed)", "Retail Shop",
"StartHub Branded Event", "StartHub Showcase", "SMB Online Store",
"SMB Tactical Program", "StarHub Biz Referral App", "Web to Lead", "Wholesale"

DEFAULT: Use "1800 Sales Hotline" unless the call summary indicates a different source.

## PRODUCT ENQUIRED VALUES (optional - use ONLY one of these exact values if applicable):
"5G", "Anti-Web Defacement (AWD)", "Apple Automated Device Enrollment (ADE)", "Apple DEP",
"Argonar", "Autodesk - Reseller", "Autodesk - User", "Bandwidth on demand", "BaseKit",
"Broadband", "Broadband Promo", "Broadband Recontract", "Business Mobile Plans",
"Business Wireless Broadband (4G)", "Business Wireless Broadband (4G) Promo",
"Cablemap", "Clean Pipe", "Cloud Connect", "Cloud Services", "Cloud Services - Backup",
"Cloud Services - DR", "Compliant Mobile Recording", "Connected Building",
"Connected Communities", "Connected Vehicles", "Cyber Security", "Cyber Security – CASB",
"Cyber Security – Cloud (Wedge)", "Cyber Security – CTM", "Cyber Security – Incident Response",
"Cyber Security – SCADA", "Cyber Security – UTM", "Data Centre", "Data Centre Promo",
"DataJump", "DC Net", "Deskera", "Device Subscription Service (HP)",
"Device Subscription Service (HP) - Promo", "Digital Transformation Solutions",
"Digital Workplace", "DualConnect", "E-invoice", "ELL", "ELL - Low Latency",
"Enterprise ID", "Enterprise Internet", "Enterprise Managed Mobility",
"Enterprise Messaging", "Enterprise Search Engine", "Enterprise Wifi",
"ePayroll", "ePayroll Promo", "eShop Builder", "Exchange Online",
"Expanding Internationally", "Expanding Locally", "Facial Recognition",
"Fleet Manager", "Global VPN", "Google Android Zero-Touch", "Hybrid Cloud",
"IDD", "IEPL", "Interactive TV", "International Roaming", "IOT", "IPLC",
"IP Transit", "ISDN", "M2M", "M2M Router", "Managed EDR", "Managed Services",
"Manage Multilink", "MaxMobile Plans", "Migration Wiz", "Mobile Broadband",
"Mobile - Data Upsize", "Mobile Office", "Mobile Plans", "Mobile Promo",
"Mobile Recontract", "Mobile - Smart Support", "Mobile - SMS Upsize",
"Mobile - Split Billing", "Mobile Threat Defence", "Mobile - Voice Upsize",
"Monthly DataRoam Basic", "Office 365", "Office 365 Promo", "Office Phone Promo",
"OLS-Bulk", "OLS-Existing", "OLS-New", "OLS Re-signup", "OLS-SmartShare",
"Partner Referrals", "Partnership Promo", "Plus 3", "Relocating Locally",
"Robotic Process Automation", "Robotics", "Samsung Knox Mobile Enrollment (KME)",
"SDS", "SD-WAN", "Setting up new business", "SIM only Plans", "SIP Voice",
"Skype for Business", "SmartBusiness", "Smart Conferencing Audio",
"Smart Conferencing Web", "SmartDigital", "Smart Engagement", "SmartHub",
"Smart Office Suite", "Smart Office Suite Promo", "SmartPTT",
"Smart Retail Suite", "Smart Retail Suite Promo", "SmartSecure", "SmartShare",
"SmartSIP for Teams Calling", "SmartSupport", "SmartUC", "SmartUC Converged",
"SmartUC Fixed", "SmartUC Mobile", "SME Brand Campaign",
"Social Listening - Curiosity", "StarHub TV", "Switch-E", "TV Promo",
"Velocity CDN", "Web Application Firewall", "WebNic", "Wireless@SG", "Workforce Manager"

## MOBILE TYPE VALUES:
"Local", "Foreign"

## LEAD CURRENCY VALUES:
"SGD", "USD"

## NAME PARSING:
- If name has multiple parts: last part = familyName, rest = givenName
- If only one name: use as familyName, omit givenName
- If no name found: familyName = "Unknown Customer"

## CRITICAL SANITIZATION RULES:
1. NEVER include fields with "N/A", "null", "None", "unknown", or empty values. OMIT the field entirely instead.
2. If recordTypeId is "N/A" or empty → DO NOT include recordTypeId in the output at all.
3. If ownerId is "N/A" or empty → DO NOT include ownerId in the output at all.
4. brn (Business Registration Number) → max 10 characters. If BRN is unknown, placeholder, "generated: XXX", or longer than 10 chars → DO NOT include brn at all.
5. DO NOT include any field whose value is null, empty string, or a placeholder.
6. Only include optional fields if they have real, meaningful values extracted from the call summary.
7. leadRemarks → max 500 characters. Summarize briefly.

## REQUIRED OUTPUT:
Return ONLY valid JSON. No markdown, no code blocks, no explanations.
Only include fields that have real values. OMIT any field where the value is unknown or placeholder.

MANDATORY fields (always include):
{{
  "familyName": "string",
  "name": "string (company name)",
  "email": "string (use placeholder@starhub.com if not found)",
  "source": "1800 Sales Hotline",
  "serviceTypeEnquired": "string (from SERVICE TYPE VALUES above)",
  "leadCurrency": "SGD",
  "status": "Open Lead"
}}

OPTIONAL fields (include ONLY if real value exists — omit entirely otherwise):
  "givenName", "mobilePhone", "mobileType", "productEnquired",
  "customerType", "leadRemarks", "salutation",
  "brn" (max 10 chars, omit if unknown),
  "recordTypeId" (omit if "{record_type_id}" is "N/A"),
  "ownerId" (omit if "{owner_id}" is "N/A")"""


DEFAULT_TMF_CONTENT_VERSION_PAYLOAD_PROMPT = """You are a Salesforce ContentVersion data assistant. Given a lead ID and call summary file details, generate a JSON payload to create a ContentVersion record via the BSSMagic TMF API to attach the call summary file to the lead.

## LEAD ID:
{lead_id}

## FILE NAME:
{file_name}

## FILE CONTENT (base64 encoded):
{file_content_b64}

## FIELD MAPPING (BSSMagic FDW view columns):
The payload MUST use these exact field names:
- title → Title (the file name without extension, MANDATORY)
- pathOnClient → PathOnClient (full file name with extension, MANDATORY)
- versionData → VersionData (base64-encoded file content, MANDATORY)
- firstPublishLocationId → FirstPublishLocationId (the Lead ID to link to, links file directly to the record)
- fileType → CPQ_File_Type__c (MANDATORY per Axway spec, default "Others")
- description → Description (optional description of the file)

## IMPORTANT:
- fileType MUST be set to "Others" (this maps to the mandatory CPQ_File_Type__c field)
- firstPublishLocationId links the uploaded file directly to the Lead record,
  eliminating the need for a separate ContentDocumentLink step

## REQUIRED OUTPUT:
Return ONLY valid JSON. No markdown, no code blocks.
{{
  "title": "{file_name} - Call Summary",
  "pathOnClient": "{file_name}",
  "versionData": "{file_content_b64}",
  "firstPublishLocationId": "{lead_id}",
  "fileType": "Others",
  "description": "Call summary attached to lead {lead_id}"
}}"""


DEFAULT_TMF_RECORD_TYPE_QUERY_PROMPT = """You are a Salesforce Lead classification assistant. Given a call summary, determine the correct Lead RecordType and generate a SOQL query to fetch its Id.

## CALL SUMMARY:
{call_summary}

## CLASSIFICATION RULES:
Analyze the call summary and determine which business segment this lead belongs to:

1. **EBG (Enterprise Business Group)** — Large enterprises, government, MNCs. Indicators:
   - Company is a known large enterprise, MNC, or government entity
   - Mentions "enterprise", "corporate", "government", "MNC"
   - Dedicated internet, MPLS, SD-WAN, large bandwidth (1Gbps+)
   - Multiple office locations, large employee count
   
2. **CBG (Consumer Business Group)** — Individual consumers, residential. Indicators:
   - Individual customer (no company or personal use)
   - Residential broadband, personal mobile plans
   - Home services

3. **SMB / SME (Small-Medium Business)** — Small to medium businesses. Indicators:
   - Small company, startup, SME, local business
   - Basic business broadband, business mobile plans
   - Fewer than ~200 employees

If unclear, default to **EBG** (most 1800 Sales Hotline calls are enterprise).

## SOQL QUERY RULES:
- Object: RecordType
- SELECT: Id, Name, SObjectType
- WHERE: SObjectType = 'Lead' AND Name LIKE '%<segment>%'
- LIMIT 5
- The Name field typically contains the segment: "EBG Lead", "CBG Lead", "SMB Lead", etc.

## REQUIRED OUTPUT:
Return ONLY a valid JSON object with:
- "segment": the identified segment (eBG, CBG, SMB)
- "reasoning": one sentence explaining why
- "query": the SOQL query string

{{"segment": "EBG", "reasoning": "Enterprise customer requesting dedicated internet services", "query": "SELECT Id, Name, SObjectType FROM RecordType WHERE SObjectType = 'Lead' AND Name LIKE '%EBG%' LIMIT 5"}}"""


DEFAULT_TMF_PRODUCT_QUERY_PROMPT = """You are a product matching assistant for BSSMagic TMF API. Given product details from a sales call, generate a SOQL query to find matching products in Salesforce CPQ.

## PRODUCT DETAILS:
{product_details}

## RELAXATION LEVEL:
{relax_level}

## CRITICAL QUERY RULES:
1. SELECT clause: ONLY use these three columns: Id, Name, cspmb__Price_Item_Code__c
2. FROM clause: ONLY cspmb__Price_Item__c
3. WHERE clause: ONLY filter by "Name" column using LIKE. NO other columns exist for filtering.
   - NEVER use Bandwidth__c, cspmb__Bandwidth__c, Features__c, or any other column — they do NOT exist.
   - To match bandwidth, include it in the Name LIKE pattern (e.g., Name LIKE '%300Mbps%' or Name LIKE '%500 Mbps%')
4. LIMIT: Use 10 for strict, 20 for relaxed queries.

## REAL PRODUCT NAME PATTERNS IN THE CATALOG:
Products follow these naming conventions — use these patterns for LIKE matching:
- Internet: "3PP Internet - 300Mbps", "3PP Internet - 1Gbps", "Assured Internet"
- Broadband: "SH Fibre Business Broadband (Dynamic IP) 500 Mbps", "SH Fibre Business Broadband (Static IP) 1 Gbps"
- Wireless: "Business Wireless Broadband 4G (Dynamic IP) 100 GB", "Static Wireless Broadband"
- Mobile: "Mobile", "MaxMobile Elite (6GB) DataPack", "Legacy Mobile Plan"
- Voice: "SmartUC", "StarHub O.N.E Phone", "SIP Voice"
- SD-WAN: "SD-WAN"

## RELAXATION RULES:
- R0 (strict): Match specific product name with bandwidth in Name LIKE pattern
  Example: Name LIKE '%Internet%300Mbps%' or Name = 'Assured Internet'
- R1 (bandwidth_relax): Broaden bandwidth range in Name patterns
  Example: Name LIKE '%Internet%' AND (Name LIKE '%300%' OR Name LIKE '%500%')
- R2 (mobile_first): Add mobile/wireless/broadband alternatives
  Example: (Name LIKE '%Internet%' OR Name LIKE '%Mobile%' OR Name LIKE '%Broadband%')
- R3 (unlimited_relax): Remove bandwidth from Name filter entirely
  Example: Name LIKE '%Internet%' OR Name LIKE '%Broadband%'
- R4 (category_expand): Broadest search across all categories
  Example: Name LIKE '%Internet%' OR Name LIKE '%Mobile%' OR Name LIKE '%Broadband%' OR Name LIKE '%Wireless%'

## REQUIRED OUTPUT:
Return ONLY a valid JSON object with a "query" field containing the full SOQL query string.
No markdown, no code blocks, no explanations.

{{"query": "SELECT Id, Name, cspmb__Price_Item_Code__c FROM cspmb__Price_Item__c WHERE Name LIKE '%pattern%' LIMIT 10"}}"""


DEFAULT_TMF_PRICING_QUERY_PROMPT = """You are a pricing query assistant for BSSMagic TMF API. Given product IDs found from Salesforce, generate a query to fetch their pricing details.

## PRODUCT IDS:
{product_ids}

## PRODUCT NAMES:
{product_names}

## TARGET OBJECT: cspmb__Price_Item__c
The pricing fields are on the Price Item object itself (NOT on cspmb__Price_Item_Pricing_Rule_Association__c which is blocked by the API proxy).

## CRITICAL RULES:
1. SELECT clause: Use Id, Name, cspmb__One_Off_Charge__c, cspmb__Recurring_Charge__c, cspmb__One_Off_Cost__c, cspmb__Recurring_Cost__c, cspmb__Contract_Term__c, cspmb__Is_Active__c, CurrencyIsoCode
   - NEVER use relationship fields (X__r.Y) — they cause errors.
2. WHERE clause: Use Id IN (...) with single-quoted IDs.
   - Add: CurrencyIsoCode = 'SGD' (exact case: CurrencyIsoCode)
3. Include AT MOST 5 product IDs. If more than 5 IDs are provided, pick the 5 most relevant ones based on the product names.
4. LIMIT 20

## REQUIRED OUTPUT:
Return ONLY a valid JSON object with a "query" field.
No markdown, no code blocks, no explanations.

{{"query": "SELECT Id, Name, cspmb__One_Off_Charge__c, cspmb__Recurring_Charge__c, cspmb__One_Off_Cost__c, cspmb__Recurring_Cost__c, cspmb__Contract_Term__c, cspmb__Is_Active__c, CurrencyIsoCode FROM cspmb__Price_Item__c WHERE Id IN ('id1', 'id2', 'id3') AND CurrencyIsoCode = 'SGD' LIMIT 20"}}"""


DEFAULT_TMF_SFDC_ACTIONS_COMPILE_PROMPT = """You are a CRM action report compiler. Given all the API call results from BSSMagic TMF operations for a single sales call, compile them into a final structured sfdc-actions.json.

## TASK ID:
{task_id}

## CALL SUMMARY:
{call_summary}

## PRODUCT DETAILS:
{product_details}

## CRM OPERATIONS LOG:
{operations_log}

## COMPILATION RULES:
1. Summarize each operation (lead creation, file attachment, product queries, pricing queries)
2. For each operation include: type, action, success/failure, record IDs, key details
3. Include a final summary with: total_operations, successful, failed
4. Include product matching results with: matched products, pricing found, best match
5. If any operation failed, include error details

## REQUIRED OUTPUT FORMAT:
{{
  "task_id": "{task_id}",
  "executed_at": "[current ISO timestamp]",
  "success": true|false,
  "summary": {{
    "total_operations": 0,
    "successful": 0,
    "failed": 0,
    "lead_created": true|false,
    "lead_id": "string or null",
    "file_attached": true|false,
    "products_matched": 0,
    "pricing_found": true|false
  }},
  "actions": [
    {{
      "type": "lead|attachment|product_query|pricing_query",
      "action": "created|attached|queried",
      "record_id": "string or null",
      "success": true|false,
      "details": {{}},
      "error": "string or null"
    }}
  ],
  "products": [
    {{
      "requested_product": "string",
      "matched_product_id": "string or null",
      "matched_product_name": "string or null",
      "relaxation_level": "R0|R1|R2|R3|R4",
      "one_off_price": null,
      "recurring_price": null,
      "currency": "SGD"
    }}
  ],
  "errors": []
}}

Return ONLY valid JSON. No markdown, no code blocks, no explanations."""


# Default prompts dictionary
DEFAULT_PROMPTS: Dict[str, Dict[str, Any]] = {
    PromptType.CALL_SUMMARY.value: {
        "id": PromptType.CALL_SUMMARY.value,
        "name": "Call Summary",
        "description": "Generates a concise one-paragraph summary of a sales call including customer details, products discussed, and key requirements.",
        "content": DEFAULT_CALL_SUMMARY_PROMPT,
        "max_length": 10000,
        "placeholders": ["transcript_text", "call_id", "agent_name", "customer_company", "call_date"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.PRODUCT_DETAILS.value: {
        "id": PromptType.PRODUCT_DETAILS.value,
        "name": "Product Details",
        "description": "Extracts structured product information from a sales call transcript as JSON, including product names, types, pricing, and customer interest levels.",
        "content": DEFAULT_PRODUCT_DETAILS_PROMPT,
        "max_length": 10000,
        "placeholders": ["transcript_text", "call_id", "customer_company", "call_date"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.SF_CREATE_LEAD_PAYLOAD.value: {
        "id": PromptType.SF_CREATE_LEAD_PAYLOAD.value,
        "name": "Salesforce Lead Payload",
        "description": "Generates JSON payload for creating Salesforce Leads. Supports both Axway API (camelCase) and Salesforce Direct API (PascalCase) formats based on connector_type.",
        "content": DEFAULT_SF_CREATE_LEAD_PAYLOAD_PROMPT,
        "max_length": 10000,
        "placeholders": ["connector_type", "call_summary", "product_details"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.SF_DEAL_QUERY.value: {
        "id": PromptType.SF_DEAL_QUERY.value,
        "name": "Salesforce Product Query",
        "description": "Generates SOQL query to find matching products (cspmb__Price_Item__c) in Salesforce based on product details from a call.",
        "content": DEFAULT_SF_DEAL_QUERY_PROMPT,
        "max_length": 10000,
        "placeholders": ["product_details"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.SF_PRICING_QUERY.value: {
        "id": PromptType.SF_PRICING_QUERY.value,
        "name": "Salesforce Pricing Query",
        "description": "Generates SOQL query to fetch pricing information for identified products from Salesforce CPQ.",
        "content": DEFAULT_SF_PRICING_QUERY_PROMPT,
        "max_length": 10000,
        "placeholders": ["product_ids", "product_names"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.SF_RESPONSE_COMPILE.value: {
        "id": PromptType.SF_RESPONSE_COMPILE.value,
        "name": "Salesforce Response Compiler",
        "description": "Compiles Salesforce/Axway API responses into structured sfdc_action.json format for CRM action tracking.",
        "content": DEFAULT_SF_RESPONSE_COMPILE_PROMPT,
        "max_length": 15000,
        "placeholders": ["operation_type", "api_response", "transcript_analysis", "task_id"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    # ── TMF / BSSMagic Prompts ──
    PromptType.TMF_LEAD_PAYLOAD.value: {
        "id": PromptType.TMF_LEAD_PAYLOAD.value,
        "name": "TMF Lead Payload (BSSMagic)",
        "description": "Generates JSON payload for creating a Lead via BSSMagic TMF API. Uses FDW view column names (familyName, givenName, etc.) that map to Salesforce Lead fields. Includes complete Axway picklist values for serviceTypeEnquired, leadSource, and productEnquired.",
        "content": DEFAULT_TMF_LEAD_PAYLOAD_PROMPT,
        "max_length": 20000,
        "placeholders": ["record_type_id", "owner_id", "call_summary", "product_details"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.TMF_CONTENT_VERSION_PAYLOAD.value: {
        "id": PromptType.TMF_CONTENT_VERSION_PAYLOAD.value,
        "name": "TMF ContentVersion Payload (BSSMagic)",
        "description": "Generates JSON payload for attaching call summary file to a Lead via BSSMagic TMF ContentVersion endpoint using FirstPublishLocationId.",
        "content": DEFAULT_TMF_CONTENT_VERSION_PAYLOAD_PROMPT,
        "max_length": 10000,
        "placeholders": ["lead_id", "file_name", "file_content_b64"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.TMF_RECORD_TYPE_QUERY.value: {
        "id": PromptType.TMF_RECORD_TYPE_QUERY.value,
        "name": "TMF RecordType Query (BSSMagic)",
        "description": "AI-driven Lead RecordType classification. Analyzes call summary to determine business segment (EBG/CBG/SMB) and generates SOQL query for the matching RecordType.",
        "content": DEFAULT_TMF_RECORD_TYPE_QUERY_PROMPT,
        "max_length": 5000,
        "placeholders": ["call_summary"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.TMF_PRODUCT_QUERY.value: {
        "id": PromptType.TMF_PRODUCT_QUERY.value,
        "name": "TMF Product Query (BSSMagic)",
        "description": "Generates SOQL query for finding matching products in Salesforce CPQ via BSSMagic TMF ProductOffering endpoint. Supports R0-R4 relaxation levels for progressive matching.",
        "content": DEFAULT_TMF_PRODUCT_QUERY_PROMPT,
        "max_length": 10000,
        "placeholders": ["product_details", "relax_level"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.TMF_PRICING_QUERY.value: {
        "id": PromptType.TMF_PRICING_QUERY.value,
        "name": "TMF Pricing Query (BSSMagic)",
        "description": "Generates SOQL query for fetching pricing rules from Salesforce CPQ via BSSMagic TMF ProductOfferingPrice endpoint.",
        "content": DEFAULT_TMF_PRICING_QUERY_PROMPT,
        "max_length": 10000,
        "placeholders": ["product_ids", "product_names"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    },
    PromptType.TMF_SFDC_ACTIONS_COMPILE.value: {
        "id": PromptType.TMF_SFDC_ACTIONS_COMPILE.value,
        "name": "TMF SFDC Actions Compiler",
        "description": "Compiles all BSSMagic TMF CRM operation results into the final sfdc-actions.json with lead details, file attachment status, product matches, and pricing information.",
        "content": DEFAULT_TMF_SFDC_ACTIONS_COMPILE_PROMPT,
        "max_length": 20000,
        "placeholders": ["task_id", "call_summary", "product_details", "operations_log"],
        "is_default": True,
        "updated_at": None,
        "updated_by": None
    }
}


def get_default_prompts() -> List[PromptEntry]:
    """Get list of default prompt entries"""
    return [PromptEntry(**prompt_data) for prompt_data in DEFAULT_PROMPTS.values()]


def get_default_prompt(prompt_id: str) -> Optional[PromptEntry]:
    """Get a specific default prompt by ID"""
    if prompt_id in DEFAULT_PROMPTS:
        return PromptEntry(**DEFAULT_PROMPTS[prompt_id])
    return None
