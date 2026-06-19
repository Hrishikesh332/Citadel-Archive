# Citadel Mesh Architecture Research

Date: 2026-05-27

This brief grounds the Citadel knowledge-mesh UI in the actual product models behind Obsidian, Outline, and Data Mesh. The previous visual direction treated "mesh" too literally. The product should not lead with a decorative 3D network. It should lead with a serious knowledge operations workspace.

## Design Verdict

The strongest direction is:

**Outline-style knowledge base shell + Obsidian-style relationship discovery + Data Mesh product/governance model.**

The graph is not the main product. The main product is trusted knowledge and data-product operations: who owns a thing, what it depends on, who consumes it, what contract governs it, whether it is fresh, and what documentation explains it.

## Primary Sources Checked

- Obsidian releases and ecosystem: https://github.com/obsidianmd/obsidian-releases
- Obsidian data storage: https://obsidian.md/help/data-storage
- Obsidian links: https://obsidian.md/help/links
- Obsidian backlinks: https://obsidian.md/help/plugins/backlinks
- Obsidian graph view: https://obsidian.md/help/plugins/graph
- Obsidian canvas: https://obsidian.md/help/plugins/canvas
- Obsidian workspace and tabs: https://obsidian.md/help/workspace, https://obsidian.md/help/tabs
- Obsidian developer manifest: https://docs.obsidian.md/Reference/Manifest
- Outline repo: https://github.com/outline/outline
- Outline product site: https://www.getoutline.com/
- Outline guide: https://docs.getoutline.com/s/guide
- Outline terminology: https://docs.getoutline.com/s/guide/doc/terminology-fKoXA2YGzH
- Outline collections: https://docs.getoutline.com/s/guide/doc/collections-l9o3LD22sV
- Outline search and AI answers: https://docs.getoutline.com/s/guide/doc/search-ai-answers-NIKPvYrx06
- Outline formatting and blocks: https://docs.getoutline.com/s/guide/doc/formatting-kn6wBtxlQ1, https://docs.getoutline.com/s/guide/doc/blocks-iwAQVA8kAf
- Outline architecture: https://github.com/outline/outline/blob/main/docs/ARCHITECTURE.md
- Data Mesh Architecture: https://www.datamesh-architecture.com/
- Data Mesh Canvas: https://www.datamesh-architecture.com/data-mesh-canvas
- Data Product Canvas: https://www.datamesh-architecture.com/data-product-canvas
- Data Product Specification: https://dataproduct-specification.com/
- Data Contract Specification: https://datacontract.com/
- Zhamak Dehghani on Data Mesh principles: https://martinfowler.com/articles/data-mesh-principles.html

## Obsidian Fundamentals

Obsidian is a local-first Markdown workspace. A vault is a folder on the local file system. Notes are plain text Markdown. Settings live inside a vault-level `.obsidian` folder. This matters because the product starts from durable documents, not a cloud object diagram.

Obsidian combines several navigation models:

- File/folder hierarchy for predictable organization.
- Internal links for associative knowledge.
- Backlinks and unlinked mentions for reverse context and suggested relationships.
- Tags/properties for structured metadata.
- Search and command palette for fast retrieval.
- Graph view and Canvas for visual sense-making.
- Panes, sidebars, tabs, splits, pinned tabs, linked views, and saved workspaces for task-specific layouts.

Graph view is functional. Nodes are notes, edges are internal links, larger nodes represent more references, and users can pan, zoom, filter, group, tune forces, and open a local graph around the active note with depth controls. A useful graph explains relationships around the active object. A whole-vault graph is often noise.

Canvas is also functional: an infinite 2D surface for notes, cards, media, web pages, groups, and labeled connections. It is a workbench for thinking, not the default operating screen.

The ecosystem is central. The releases repo hosts public releases and community plugin/theme directories, not the core source code. Current directory scale checked from the official JSON lists: roughly 4,184 community plugins and 531 themes. This proves the Obsidian mental model is extensibility, user-shaped workspaces, and plugin-like modules.

Design implications:

- Lead with document and workspace primitives.
- Use local graph as context around the active product or document.
- Make backlinks, outgoing links, and possible unlinked mentions first-class.
- Support properties/metadata panels, filters, saved views, and keyboard command flow.
- Do not use a global 3D graph as the first screen.

## Outline Fundamentals

Outline is a team knowledge base. Its model is:

`Workspace -> Collections -> Documents -> Nested child documents`

A workspace is the top-level organization. Collections organize documents by high-level topics or teams and also act as permission boundaries. Documents are the main writing and reading surface. Documents can be nested into trees and can act like folders.

Outline's core strengths are:

- Clear sidebar navigation around collections and nested docs.
- Fast editor surface with Markdown support, slash commands, blocks, tables, embeds, diagrams, and comments.
- Realtime collaboration.
- Search and AI answers that respect user permissions.
- Sharing: internal document sharing, public document/collection links, and custom branded public docs.
- Roles and permissions: admin, editor, viewer, guest, groups, collection permissions, and document/subtree sharing.
- Export to Markdown, HTML, or JSON for portability.

The repo architecture confirms this product shape. The frontend is React/Vite with MobX and Styled Components. The shared editor is ProseMirror-based. Backend authorization lives in policy files, and collection/document permissions are core implementation concepts.

Design implications:

- The shell should be a calm, dense knowledge-base interface.
- Left navigation should be hierarchical and domain/collection oriented.
- Center should be a readable document or data-product page.
- Right side should expose ownership, permissions, trust, backlinks, lineage, and activity.
- Search and command should be available globally.
- Collaboration, access state, comments, and history should feel native, not bolted on.

## Data Mesh Fundamentals

Data Mesh is not a visual mesh. It is a sociotechnical architecture for analytical data at scale. It exists because central data teams and centralized lakes become bottlenecks when many domains need fast, trustworthy data.

The four principles are:

1. Domain-oriented decentralized ownership.
2. Data as a product.
3. Self-serve data infrastructure as a platform.
4. Federated computational governance.

A data product is the key object. It is a consumable unit owned by a domain team. It contains or references code, data, metadata, infrastructure, policies, contracts, quality metrics, and output ports. It is operated through its lifecycle by an accountable team.

The Data Product Canvas defines the detail model:

- Domain
- Data Product Name
- Consumer and Use Case
- Data Contract
- Sources
- Data Product Architecture
- Ubiquitous Language
- Classification

The Data Product Canvas also forces questions that the UI must answer:

- Who owns this?
- Who uses it?
- What problem/use case does it serve?
- What inputs does it depend on?
- What output ports does it expose?
- What contract governs usage?
- What quality/SLA/security expectations apply?
- Is it source-aligned, aggregate, or consumer-aligned?

The Data Mesh Canvas maps the broader landscape. Its useful visual model is lane-based, not 3D:

- Source-aligned data products
- Aggregate data products
- Consumer-aligned data products

Data products sit inside domain/team ownership areas, and directed connections show dependency or consumption flow.

Design implications:

- The UI object model must be domain-first and product-first.
- Every node needs ownership, contract, quality, access, lifecycle, source, consumer, and governance status.
- Governance should be computationally visible: pass/fail checks, missing metadata, policy conflicts, freshness, PII/access warnings.
- The mesh map should show lineage and product archetypes, not decorative points.

## Combined Product Model

The combined model should be:

`Workspace -> Domain -> Data Product -> Docs / Contract / Sources / Outputs / Consumers / Decisions / Quality / Lineage / Policies`

Mapping the references:

- Outline workspace maps to the top-level Citadel workspace.
- Outline collections map to domains or teams.
- Outline documents map to readable docs, decisions, runbooks, specs, and product notes.
- Obsidian links/backlinks map to knowledge relationships, lineage hints, citations, and unlinked possible relationships.
- Obsidian graph maps to local relationship exploration around the active object.
- Data Mesh data products map to first-class operational objects.
- Data contracts map to API/schema/terms/quality/access metadata.
- Data Mesh Canvas maps to the landscape/workshop view.
- Data Product Canvas maps to the product detail/create/edit view.

Relationship types should be explicit:

- `depends_on`
- `consumes`
- `produces`
- `documents`
- `references`
- `owned_by`
- `governed_by`
- `supersedes`
- `mentions`
- `violates_policy`

## Recommended UI Architecture

### 1. Domain Command Center

Default screen. This is the serious first viewport.

- Left: domains/collections, saved views, recent docs, product catalog.
- Top: command/search, filters, environment/status, create button.
- Center: selected data product or domain overview.
- Right: trust inspector with owner, contract, freshness, quality, access, consumers, upstream/downstream lineage, open incidents.
- Bottom or secondary panel: local graph around selected product.

### 2. Data Product Detail Page

This should be the hero object for a product-focused page.

- Product title, domain, owner, lifecycle.
- Contract version and output ports.
- Consumer/use case list.
- Sources and lineage.
- Quality/SLA/freshness checks.
- Security/access/PII classification.
- Docs, decisions, changelog, incidents.
- Local graph: 1-hop and 2-hop dependencies only.

### 3. Data Product Canvas Workbench

Secondary mode for designing or auditing a product.

- Eight canvas blocks from the Data Product Canvas.
- Validation state per block.
- Missing metadata warnings.
- Convert canvas into contract/product spec.

### 4. Mesh Map

Advanced mode, not the landing screen.

- Lane-based source-aligned / aggregate / consumer-aligned map.
- Ownership zones by domain/team.
- Directed edges for source/consumer flow.
- Filters by owner, archetype, access, quality, freshness, policy, consumer.
- Click opens inspector or product page.

### 5. Knowledge Graph Explorer

Advanced mode for discovery.

- Local graph by default.
- Depth control.
- Incoming/outgoing/unlinked possible connections.
- Edge labels explaining relationship type.
- Node size based on references or downstream consumers.
- Colors by domain or archetype.

## What The Current Prototype Got Wrong

- It still over-indexes on a hero-like visual.
- It treats the graph as the main idea instead of a contextual tool.
- It does not make ownership, contracts, freshness, access, governance, and quality feel central enough.
- It lacks a believable document/editor surface.
- It lacks a clear operational object model.
- It shows concepts, but not enough workflow.

## Concrete Rebuild Direction

Rebuild the HTML mock as a product screen, not a design wall:

1. First viewport: Domain Command Center.
2. Selected object: `Knowledge Mesh` as a data product.
3. Left nav: domains and nested docs like Outline.
4. Center: data product overview with contract, docs, decisions, consumers, and incidents.
5. Right: trust/governance inspector.
6. Lower center: local graph/lineage mini-map with explainable edges.
7. Secondary tabs: `Docs`, `Contract`, `Lineage`, `Canvas`, `Governance`.

The visual tone should be quiet, dense, and operational. Think internal platform console, not sci-fi network.
