# Speaker notes

IAEG 2026, Monday 2 November, 15:00, Hall A, session 1.1.1. 10 minutes and 5 for questions. Each `##` heading is the `id` of a slide in `studio/presentation_notebook/slides/src/slides.json`, and `build_pptx.py` puts its text in that slide's PowerPoint notes.

## title

*0:20*

Good afternoon, I'm Joost Gevaert from Bedrock.engineer. In the next ten minutes I'll show how to build an engineering geological model of soft soil from public data with open-source tools, and how to get it in front of the people who design on top of it.

## problem

*1:00*

Two problems. First, in a coastal-deltaic setting, much of the variability that matters sits inside a single geological unit. Paleochannels don't form continuous layers, so geological modeling software that draws surfaces between units can't represent them.

Second, the model usually stops with us. Designers, contractors and regulators work in BIM and 3D GIS, and what they get from us is a PDF with cross-sections.

This picture is where we want to go: the ground, with its channel sands, right under the piles of a building.

## pipeline

*1:10*

This is the whole workflow as a pipeline: data, process, data. It follows the IAEG C25 guidelines, where an EGM integrates a conceptual model with observations.

The conceptual part is the geology. GemPy, the dashed branch at the top, brings the structural modeling into the workflow, so that the geological model updates when new boreholes arrive. In today's demo that branch isn't connected yet: the model starts from GeoTOP's units directly.

The observational part is the CPTs. Within each domain we simulate CPT parameters, and soil types follow from those per realization. That's common practice: NGI's TNW offshore ground model works this way too. When new CPTs arrive, you rerun it.

## data

*0:40*

The site is at Overhoeks in Amsterdam Noord, next to the EYE film museum. Everything here comes from the Dutch Registry of the Subsurface: the GeoTOP voxel model and 85 CPTs.

These are GeoTOP's voxels among the 3D BAG buildings. They're a hundred by a hundred meters by half a meter. They carry the regional stratigraphy, but not the variability a foundation engineer cares about.

## domains

*1:00*

The guidelines are clear that engineering geological units shouldn't cross lithostratigraphic boundaries. So we group GeoTOP's units into six simulation domains, and a unit the CPTs barely reach gets pooled with its neighbors.

This chart shows why that's a sensible grouping: the median cone resistance runs from about half a megapascal to about twenty, while each bar shows the spread within a domain. That spread is what we simulate.

Each domain gets its own variogram, fitted along and between the CPTs. I won't go into those here, because the geostatistics aren't the point of this talk.

## simulation

*1:30*

This is the result: conditional Gaussian simulation with GSTools, in each domain, in ten realizations. fs is co-simulated with qc, so each realization keeps their relation, and a classification such as Robertson's can be derived per realization rather than simulated.

Here you see the median qc, in plan and in two cross-sections, as I move through the model. And now each realization in turn.

Close to a CPT they agree, and between CPTs they differ. That difference is the point: variability shows up inside one geological unit, without anyone drawing a surface.

## uncertainty

*0:50*

Because we have realizations, the uncertainty comes with the model. On the left, one CPT: the realizations follow its data. On the right, a section with the ratio of P90 to P10 of qc.

That's a map of where we don't know, and so of where the next CPT would be worth the most. It's the kind of reliability statement the C25 guidelines ask for.

## bim

*1:20*

And this is what the designer gets. To be clear, this building is a Revit sample project that we placed on the site for the demo, not a real design.

Under it is the model: the most likely soil type per cell, as we peel away the clay and peat. What's left are the sand bodies under the piles. It's all in real coordinates, in a web viewer built on Speckle's, among the 3D BAG. A link is enough to open it, with nothing to install.

So a designer can look at this and ask which piles land in sand, and how sure we are of that.

## close-geology

*0:40*

So, to wrap up, three things. First: geology for the units, geostatistics inside them.

That implements the EGM principle of integrating conceptual and observational components. It makes full use of the available geological and geotechnical data. And it's straightforward to update as new data comes in.

## close-accessible

*0:40*

Second, it's accessible. Because the data is in open 3D geospatial formats, it can go anywhere, and through Speckle into any BIM software.

That makes it directly usable for designers, contractors, clients and regulators. It improves communication, and it supports risk-based decision making.

## close-open

*0:30*

Third, all of this is open source. That reduces vendor lock-in, it makes the work transparent, and it gives you the flexibility to meet project-specific requirements.

## close-qr

*0:20*

All notebooks and this model are behind this QR code. Thank you, I'd love to hear your questions.
