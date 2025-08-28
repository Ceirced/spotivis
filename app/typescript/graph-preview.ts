import * as d3 from 'd3';

interface NodeData extends d3.SimulationNodeDatum {
    playlist_id: string;
    display_name?: string;
    playlist_description?: string;
    playlist_followers?: number;
    x?: number;
    y?: number;
}


interface ProcessedEdgeData extends d3.SimulationLinkDatum<NodeData> {
    source: string | NodeData;
    target: string | NodeData;
    weight: number;
}

type LinkCount = Record<string, number>;

export function createGraph(jobId: string): void {
    const graphContainer = d3.select<HTMLElement, unknown>("#graph-container");
    const containerElement = document.getElementById("graph-container");
    
    if (!containerElement) {
        console.error("Graph container not found");
        return;
    }

    const containerRect = containerElement.getBoundingClientRect();
    const width = containerRect.width;
    const height = 600;

    let nodes: NodeData[];
    let links: ProcessedEdgeData[];
    let linkCount: LinkCount = {};
    let incomingCount: LinkCount = {};
    let outgoingCount: LinkCount = {};

    function fillTooltip(data: NodeData, incoming = 0, outgoing = 0): void {
        const panel = d3.select("#graph-info-panel");
        panel.style("display", "block");

        panel.select("#node-name").text(data.display_name || data.playlist_id);
        panel.select("#node-description").text(`Description: ${data.playlist_description || "none"}`);
        panel.select("#node-followers").text(`${data.playlist_followers || 0} followers`);
        panel.select("#node-incoming").text(`${incoming} incoming connections`);
        panel.select("#node-outgoing").text(`${outgoing} outgoing connections`);
    }

    Promise.all([
        d3.csv(`/first/graph-data/${jobId}/nodes`),
        d3.csv(`/first/graph-data/${jobId}/edges`),
    ])
        .then(([rawNodes, rawEdges]) => {
            // Process nodes
            nodes = rawNodes.map((d) => ({
                playlist_id: d.playlist_id || '',
                display_name: d.display_name,
                playlist_description: d.playlist_description,
                playlist_followers: d.playlist_followers ? +d.playlist_followers : 0,
                x: Math.random() * width,
                y: Math.random() * height,
            }));

            // Process edges
            links = rawEdges.map((d) => ({
                source: d.playlist_id_1 || '',
                target: d.playlist_id_2 || '',
                weight: +(d.weight || 1),
            }));

            // Calculate link counts
            links.forEach((link) => {
                const sourceId = typeof link.source === 'string' ? link.source : link.source.playlist_id;
                const targetId = typeof link.target === 'string' ? link.target : link.target.playlist_id;
                
                linkCount[sourceId] = (linkCount[sourceId] || 0) + 1;
                linkCount[targetId] = (linkCount[targetId] || 0) + 1;
                incomingCount[targetId] = (incomingCount[targetId] || 0) + 1;
                outgoingCount[sourceId] = (outgoingCount[sourceId] || 0) + 1;
            });

            // Remove duplicate links
            links = links.filter(
                (v, i, a) =>
                    a.findIndex(
                        (t) => {
                            const vSource = typeof v.source === 'string' ? v.source : v.source.playlist_id;
                            const vTarget = typeof v.target === 'string' ? v.target : v.target.playlist_id;
                            const tSource = typeof t.source === 'string' ? t.source : t.source.playlist_id;
                            const tTarget = typeof t.target === 'string' ? t.target : t.target.playlist_id;
                            return tSource === vSource && tTarget === vTarget;
                        }
                    ) === i
            );

            // Clear skeleton loader
            graphContainer.selectAll("*").remove();

            // Create SVG
            const svg = graphContainer
                .append("svg")
                .attr("width", width)
                .attr("height", height);

            // Create a group for zoom behavior
            const g = svg.append("g");

            function nodeSize(d: NodeData): number {
                return Math.sqrt(outgoingCount[d.playlist_id] || 1) * 4;
            }

            function zoomed(event: d3.D3ZoomEvent<SVGSVGElement, unknown>): void {
                g.attr("transform", event.transform.toString());
            }

            // Define zoom behavior
            const zoom = d3
                .zoom<SVGSVGElement, unknown>()
                .scaleExtent([0.2, 10])
                .on("zoom", zoomed);

            svg.call(zoom);

            // Add definitions for markers and gradients (keep in svg, not in g)
            const defs = svg.append("defs");

            defs.selectAll("marker")
                .data(["end"])
                .enter()
                .append("marker")
                .attr("id", String)
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 15)
                .attr("refY", -1.5)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("svg:path")
                .attr("d", "M0,-5L10,0L0,5")
                .attr("class", "fill-current");

            const gradient = defs
                .append("radialGradient")
                .attr("id", "gradient")
                .attr("cx", "50%")
                .attr("cy", "50%")
                .attr("r", "50%");

            gradient
                .append("stop")
                .attr("offset", "0%")
                .attr("stop-color", "#1ED760")
                .attr("stop-opacity", 1);
            gradient
                .append("stop")
                .attr("offset", "100%")
                .attr("stop-color", "#128C46")
                .attr("stop-opacity", 1);

            function linkOpacity(d: ProcessedEdgeData): number {
                return Math.min(d.weight / 64, 0.8);
            }

            // Create simulation
            const simulation = d3
                .forceSimulation<NodeData>(nodes)
                .force(
                    "link",
                    d3
                        .forceLink<NodeData, ProcessedEdgeData>(links)
                        .id((d: NodeData) => d.playlist_id)
                        .distance(80)
                )
                .force(
                    "collide",
                    d3.forceCollide<NodeData>().radius((d: NodeData) => nodeSize(d))
                )
                .force("charge", d3.forceManyBody<NodeData>().strength(-60))
                .force(
                    "center",
                    d3.forceCenter(width / 2, height / 2).strength(0.2)
                )
                .on("tick", ticked);

            function ticked(): void {
                link.attr("x1", (d: ProcessedEdgeData) => {
                        const source = d.source as NodeData;
                        return source.x!;
                    })
                    .attr("y1", (d: ProcessedEdgeData) => {
                        const source = d.source as NodeData;
                        return source.y!;
                    })
                    .attr("x2", (d: ProcessedEdgeData) => {
                        const target = d.target as NodeData;
                        return target.x!;
                    })
                    .attr("y2", (d: ProcessedEdgeData) => {
                        const target = d.target as NodeData;
                        return target.y!;
                    });

                node.attr("cx", (d: NodeData) => d.x!).attr("cy", (d: NodeData) => d.y!);
            }

            // Create links
            const link = g
                .append("g")
                .attr("id", "edges")
                .selectAll<SVGLineElement, ProcessedEdgeData>("line")
                .data(links)
                .enter()
                .append("line")
                .attr("class", "stroke-current")
                .attr("opacity", (d: ProcessedEdgeData) => linkOpacity(d))
                .attr("marker-end", "url(#end)");

            // Node event handlers
            function selectNode(_event: MouseEvent, d: NodeData, nodeElement: SVGCircleElement): void {
                fillTooltip(
                    d,
                    incomingCount[d.playlist_id],
                    outgoingCount[d.playlist_id]
                );

                d3.select(nodeElement)
                    .transition()
                    .duration(200)
                    .attr("r", nodeSize(d) + 5);
            }

            function deselectNode(_event: MouseEvent, d: NodeData, nodeElement: SVGCircleElement): void {
                d3.select(nodeElement)
                    .transition()
                    .duration(200)
                    .attr("r", nodeSize(d));
            }

            function highlightNeighbors(_event: MouseEvent, d: NodeData, nodeElement: SVGCircleElement): void {
                const neighbors = links
                    .filter(
                        (link) => {
                            const source = link.source as NodeData;
                            const target = link.target as NodeData;
                            return source === d || target === d;
                        }
                    )
                    .map((link) => {
                        const source = link.source as NodeData;
                        const target = link.target as NodeData;
                        return source.playlist_id === d.playlist_id ? target : source;
                    });

                const neighborsLinks = links.filter((link) => {
                    const source = link.source as NodeData;
                    const target = link.target as NodeData;
                    return source === d || target === d;
                });

                d3.selectAll("circle").attr("opacity", 0.3);
                d3.selectAll("line")
                    .filter((linkData) => !neighborsLinks.includes(linkData as ProcessedEdgeData))
                    .transition()
                    .duration(300)
                    .ease(d3.easeCubicInOut)
                    .attr("opacity", 0.05);

                d3.selectAll("line")
                    .filter((linkData) => neighborsLinks.includes(linkData as ProcessedEdgeData))
                    .transition()
                    .duration(300)
                    .ease(d3.easeCubicInOut)
                    .attr("opacity", (linkData) => linkOpacity(linkData as ProcessedEdgeData));

                d3.selectAll("circle")
                    .filter((nodeData) => neighbors.includes(nodeData as NodeData))
                    .attr("opacity", 1);

                d3.select(nodeElement).attr("opacity", 1);
            }

            // Create nodes
            const node = g
                .append("g")
                .attr("id", "nodes")
                .selectAll<SVGCircleElement, NodeData>("circle")
                .data(nodes)
                .enter()
                .append("circle")
                .attr("r", (d: NodeData) => nodeSize(d))
                .attr("fill", "url(#gradient)")
                .call(drag(simulation))
                .on("mouseover", function (event: MouseEvent, d: NodeData) {
                    selectNode(event, d, this);
                })
                .on("mouseout", function (event: MouseEvent, d: NodeData) {
                    deselectNode(event, d, this);
                })
                .on("click", function (event: MouseEvent, d: NodeData) {
                    highlightNeighbors(event, d, this);
                })

            // Reset on background click
            svg.on("click", function (event: MouseEvent) {
                const target = event.target as Element;
                if (target.tagName !== "circle") {
                    d3.selectAll("circle").attr("opacity", 1);
                    d3.selectAll("line").attr("opacity", (d) =>
                        linkOpacity(d as ProcessedEdgeData)
                    );
                    d3.select("#graph-info-panel").style("display", "none");
                }
            });

            function drag(simulation: d3.Simulation<NodeData, undefined>) {
                function dragstarted(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData): void {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                }

                function dragged(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData): void {
                    d.fx = event.x;
                    d.fy = event.y;
                }

                function dragended(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData): void {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }

                return d3
                    .drag<SVGCircleElement, NodeData>()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended);
            }
        })
        .catch((error) => {
            console.error("Error loading graph data:", error);
            graphContainer.selectAll("*").remove();
            graphContainer
                .append("div")
                .attr("class", "flex items-center justify-center h-full text-error")
                .text("Error loading graph data");
        });
}