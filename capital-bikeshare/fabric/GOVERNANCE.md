# Governance guide

This is how the bike sharing data is kept trustworthy and safe once it lives in Fabric. The data itself is public open data, so the controls here are less about secrecy and more about making sure there's one version of each number, that changes are deliberate, and that the setup is ready for data that does need protecting. Most steps take a few minutes in the Fabric portal. A few depend on tenant settings that your Fabric administrator controls; those are marked.

## Who owns what

Name a data owner, who decides who gets access and signs off on changes to measure definitions, and a technical owner, who maintains the notebooks and the model. Put both in the description and contact list of the lakehouse, the semantic model and the report (each item's Settings, About), so anyone who finds them in the OneLake catalog knows who to ask.

## Workspaces and roles

Use three workspaces: *Bike Share [Dev]*, *[Test]* and *[Prod]*. Build and change things in Dev, check them in Test, and let people use only Prod.

Keep workspace roles narrow. Admin is for the data owner and one backup. Member is for the people who publish the semantic model and reports. Contributor is for whoever runs and edits the notebooks, and only in Dev. Report readers should not be workspace members at all. Publish a Power BI app from Prod and add them to its audience, so they get the report without seeing the lakehouse or the notebooks.

Give **Build** permission on the semantic model only to analysts who should make their own reports from it. That's how you allow self-service on the agreed measures without handing out the raw tables.

## Endorsement

Mark the semantic model **Promoted** while it's in Dev and Test. Once it's in Prod and the owner has signed off on the measures, mark it **Certified**. Certification has to be switched on by your Fabric administrator, who also chooses the group allowed to certify. A certified model appears at the top of people's lists in Power BI and Excel, which steers them to it instead of copies.

## Sensitivity labels

If your organisation uses Microsoft Purview Information Protection, apply a label to the lakehouse, the semantic model and the report. *General* or *Public* fits this open data. Labels on the model pass down to reports built from it and stay on files exported to Excel, PowerPoint or PDF. Your administrator can make labelling mandatory and turn on this downstream inheritance in the tenant settings.

## Row-level and object-level security

Notebook 02 creates two roles in the semantic model.

**All data** has no filters. It's for analysts and the owners.

**Region viewers** sees trips only for stations in the regions listed against the person's sign-in in the `security_user_region` table, and it hides the `bike_number` column. Each person gets one row per region they may see, with their sign-in in lower case and a `region_name` exactly as it appears in `dim_station`. The data owner maintains that table. Changes take effect on the next model refresh.

To use the roles, open the semantic model's Security settings in Prod and add people or groups to each role. Use security groups rather than individuals, so access follows team membership. Then use "View as" on the report to check what a region viewer sees.

Keep three things in mind:

- **Workspace members bypass row-level security.** Admins, Members and Contributors of a workspace see everything regardless of role. That's another reason readers should come through the app as viewers.
- **The UCI totals aren't filtered by region.** Region viewers only lose rows from the station-based trip records. The UCI daily and hourly totals have no station, so they stay visible in full. If they should be restricted too, hide them from the role with object-level security.
- **Keep security in the semantic model.** It works with Direct Lake. Security set on the lakehouse's SQL endpoint instead can make Direct Lake queries fall back to the slower DirectQuery mode.

## Change control

Connect the Dev workspace to Git (Azure DevOps or GitHub) from Workspace settings, Git integration. The notebooks and the semantic model are then stored as code, and every change to a measure or a cleaning rule goes through a pull request the owner can review.

Move changes forward with a deployment pipeline: Dev to Test to Prod. Add deployment rules so each stage's semantic model points at that stage's lakehouse. Don't run notebook 02 against Prod directly, because it rebuilds the model. Let the pipeline carry the reviewed model there.

The measures are defined once, in notebook 02 (and listed in `model/measures.dax`). If someone needs a new number, add it there with a description, review it, and deploy it, rather than letting it be redefined inside individual reports.

## Data quality and refresh

Notebook 01 checks the data before it writes anything: every trip has a known station and date, the calendar has no gaps, station numbers are unique, and the daily and hourly totals agree. If a check fails, it stops and nothing in the lakehouse changes.

This data is historical, so it doesn't need a schedule. If you later load newer trip files, run notebook 01 from a data pipeline on a schedule, with an alert to the technical owner when it fails. Turn on automatic updates in the Direct Lake model's settings so it picks up new data as soon as the tables change.

## Lineage, catalog and audit

The workspace's lineage view shows how the files flow into the lakehouse, the model and the reports. Run impact analysis on the semantic model before any change to see every report and person that depends on it.

The table and column descriptions written by notebook 01 travel with the data into the semantic model, so they show in the Power BI field list, the OneLake catalog and Microsoft Purview.

Fabric records who viewed, exported or changed each item in the audit log. Your administrator can review it in Microsoft Purview or in the Fabric admin monitoring workspace. If export should be limited, the export settings live in the Fabric admin portal's tenant settings.

## Where the Claude dashboard fits

The interactive dashboard built in Claude sits outside Fabric's governance: its data is a copy, and its access is managed by its own sharing. Treat it as the storytelling and exploration companion, not the source of record. Its definitions match the model's measures, and README.md lists the small differences. Anything official, such as targets, board figures or anything regulated, should come from the certified semantic model.

## Checklist

- Owners named and listed on each item.
- Dev, Test and Prod workspaces, with narrow roles.
- Readers given access through an app.
- Build permission only for chosen analysts.
- Model certified in Prod.
- Sensitivity labels applied.
- Security groups added to both roles.
- `security_user_region` filled in.
- "View as" checked.
- Dev connected to Git.
- Deployment pipeline with deployment rules.
- Impact analysis run before each change.
