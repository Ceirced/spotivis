import * as d3 from 'd3';

interface NodeData extends d3.SimulationNodeDatum {
    playlist_id: string;
    display_name?: string;
    playlist_description?: string;
    playlist_followers?: number;
    x?: number;
    y?: number;
    color: string;
    time_period?: string;
}


interface ProcessedEdgeData extends d3.SimulationLinkDatum<NodeData> {
    source: string | NodeData;
    target: string | NodeData;
    weight: number;
}

type LinkCount = Record<string, number>;

interface ForceSettings {
    centerForce: number;
    chargeStrength: number;
    collisionForce: number;
    linkStrength: number;
    linkDistance: number;
    zoomLevel?: number;
    nodeSize?: number;
    lineWidth?: number;
}

interface GraphConfig {
    jobId: string;
    nodesUrl?: string;
    edgesUrl?: string;
    defaultNodeColor?: string;
    colorField?: string;
    colorMap?: Record<string, string>;
}

function loadForceSettings(): ForceSettings {
    const stored = localStorage.getItem('graphForceSettings');
    if (stored) {
        return JSON.parse(stored);
    }
    // Default values
    return {
        centerForce: 0.2,
        chargeStrength: -60,
        collisionForce: 1,
        linkStrength: 0,
        linkDistance: 80,
        zoomLevel: 1,
        nodeSize: 5,
        lineWidth: 1
    };
}

function saveForceSettings(settings: Partial<ForceSettings>): void {
    const current = loadForceSettings();
    const updated = { ...current, ...settings };
    localStorage.setItem('graphForceSettings', JSON.stringify(updated));
}

function initializeSliders(settings: ForceSettings): void {
    // Set slider values
    const centerSlider = document.getElementById("center-force") as HTMLInputElement;
    const chargeSlider = document.getElementById("charge-strength") as HTMLInputElement;
    const collisionSlider = document.getElementById("collision-force") as HTMLInputElement;
    const linkStrengthSlider = document.getElementById("link-strength") as HTMLInputElement;
    const linkDistanceSlider = document.getElementById("link-distance") as HTMLInputElement;
    const nodeSizeSlider = document.getElementById("node-size") as HTMLInputElement;
    const lineWidthSlider = document.getElementById("line-width") as HTMLInputElement;
    
    if (centerSlider) {
        centerSlider.value = settings.centerForce.toString();
        document.getElementById("center-force-value")!.textContent = settings.centerForce.toFixed(2);
    }
    if (chargeSlider) {
        chargeSlider.value = settings.chargeStrength.toString();
        document.getElementById("charge-strength-value")!.textContent = settings.chargeStrength.toString();
    }
    if (collisionSlider) {
        collisionSlider.value = settings.collisionForce.toString();
        document.getElementById("collision-force-value")!.textContent = settings.collisionForce.toFixed(1);
    }
    if (linkStrengthSlider) {
        linkStrengthSlider.value = settings.linkStrength.toString();
        document.getElementById("link-strength-value")!.textContent = settings.linkStrength.toFixed(2);
    }
    if (linkDistanceSlider) {
        linkDistanceSlider.value = settings.linkDistance.toString();
        document.getElementById("link-distance-value")!.textContent = settings.linkDistance.toString();
    }
    if (nodeSizeSlider) {
        nodeSizeSlider.value = (settings.nodeSize || 5).toString();
        document.getElementById("node-size-value")!.textContent = (settings.nodeSize || 5).toFixed(1);
    }
    if (lineWidthSlider) {
        lineWidthSlider.value = (settings.lineWidth || 1).toString();
        document.getElementById("line-width-value")!.textContent = (settings.lineWidth || 1).toFixed(1);
    }
}

export function createGraph(config: GraphConfig): void {

    const graphContainer = d3.select<HTMLElement, unknown>("#graph-container");
    const containerElement = document.getElementById("graph-container");
    
    if (!containerElement) {
        console.error("Graph container not found");
        return;
    }

    const containerRect = containerElement.getBoundingClientRect();
    const width = containerRect.width;
    const height = containerRect.height || 600; // Use container height or fallback to 600
    
    // Load settings and initialize sliders (always enabled)
    const settings = loadForceSettings();
    initializeSliders(settings);


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
        d3.csv(config.nodesUrl!),
        d3.csv(config.edgesUrl!),
    ])
        .then(([rawNodes, rawEdges]) => {
            // Process nodes with dynamic color mapping
            nodes = rawNodes.map((d) => {
                let nodeColor = config.defaultNodeColor!;
                
                // Apply color mapping if specified
                if (config.colorField && config.colorMap && d[config.colorField]) {
                    nodeColor = config.colorMap[d[config.colorField]] || nodeColor;
                }
                
                // Use direct color field if available
                if (d.color) {
                    nodeColor = d.color;
                }
                
                return {
                    playlist_id: d.playlist_id || '',
                    display_name: d.display_name,
                    playlist_description: d.playlist_description,
                    playlist_followers: d.playlist_followers ? +d.playlist_followers : 0,
                    x: Math.random() * width,
                    y: Math.random() * height,
                    color: nodeColor,
                    time_period: d.time_period
                };
            });

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
                const baseSize = settings.nodeSize || 5;
                return baseSize + Math.sqrt(outgoingCount[d.playlist_id] || 1) * 4;
            }

            function zoomed(event: d3.D3ZoomEvent<SVGSVGElement, unknown>): void {
                g.attr("transform", event.transform.toString());
                // Save zoom level to localStorage
                saveForceSettings({ zoomLevel: event.transform.k });
            }

            // Define zoom behavior
            const zoom = d3
                .zoom<SVGSVGElement, unknown>()
                .scaleExtent([0.05, 3])
                .on("zoom", zoomed)

            svg.call(zoom);
            
            // Apply saved zoom level centered on the graph
            if (settings.zoomLevel && settings.zoomLevel !== 1) {
                const centerX = width / 2;
                const centerY = height / 2;
                const transform = d3.zoomIdentity
                    .translate(centerX, centerY)
                    .scale(settings.zoomLevel)
                    .translate(-centerX, -centerY);
                svg.call(zoom.transform, transform);
            }
            
            // Prevent browser zoom when using wheel on the SVG
            svg.node()?.addEventListener("wheel", function(event: WheelEvent) {
                event.preventDefault();
            }, { passive: false });

            // Add definitions for markers and gradients (keep in svg, not in g)
            const defs = svg.append("defs");

            defs.selectAll("marker")
                .data(["end"])
                .enter()
                .append("marker")
                .attr("id", String)
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 8)
                .attr("refY", 0)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("svg:path")
                .attr("d", "M0,-5L10,0L0,5")
                .attr("fill", "#999")


            function linkOpacity(d: ProcessedEdgeData): number {
                return Math.min(d.weight / 64, 0.8);
            }

            // Create force instances with settings from localStorage
            const linkForce = d3
                .forceLink<NodeData, ProcessedEdgeData>(links)
                .id((d: NodeData) => d.playlist_id)
                .distance(settings.linkDistance)
                .strength(settings.linkStrength);
            
            const chargeForce = d3.forceManyBody<NodeData>().strength(settings.chargeStrength);

            const xForce = d3.forceX(width / 2).strength(settings.centerForce);
            const yForce = d3.forceY(height / 2).strength(settings.centerForce);

            const collisionForce = d3.forceCollide<NodeData>()
                .radius((d: NodeData) => nodeSize(d) + 3).iterations(3)
                .strength(settings.collisionForce);

            // Create simulation
            const simulation = d3
                .forceSimulation<NodeData>(nodes)
                .force("link", linkForce)
                .force("collide", collisionForce)
                .force("charge", chargeForce)
                .force("x", xForce)
                .force("y", yForce)
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
                        const source = d.source as NodeData;
                        const target = d.target as NodeData;
                        
                        // Calculate angle from source to target
                        const dx = target.x! - source.x!;
                        const dy = target.y! - source.y!;
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        
                        // Offset by target node radius + small gap for arrow
                        const targetRadius = nodeSize(target) + 2;
                        const ratio = (distance - targetRadius) / distance;
                        
                        return source.x! + dx * ratio;
                    })
                    .attr("y2", (d: ProcessedEdgeData) => {
                        const source = d.source as NodeData;
                        const target = d.target as NodeData;
                        
                        // Calculate angle from source to target
                        const dx = target.x! - source.x!;
                        const dy = target.y! - source.y!;
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        
                        // Offset by target node radius + small gap for arrow
                        const targetRadius = nodeSize(target) + 2;
                        const ratio = (distance - targetRadius) / distance;
                        
                        return source.y! + dy * ratio;
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
                .attr("stroke", '#999' )
                .attr("stroke-width", settings.lineWidth || 1)
                .attr("opacity", (d: ProcessedEdgeData) => linkOpacity(d))
                .attr("marker-end", "url(#end)")

            // Create nodes
            const node = g
                .append("g")
                .attr("id", "nodes")
                .selectAll<SVGCircleElement, NodeData>("circle")
                .data(nodes)
                .enter()
                .append("circle")
                .attr("r", (d: NodeData) => nodeSize(d))
                .attr("fill",(d: NodeData) => d.color )
                .attr("stroke", "#fff")
                .attr("stroke-width", 1.5)
                .on("mouseover", function (event: MouseEvent, d: NodeData) {
                    selectNode(event, d, this);
                })
                .on("mouseout", function (event: MouseEvent, d: NodeData) {
                    deselectNode(event, d, this);
                })
                .call(
                    drag(simulation)
                        .on("start.highlight", function (event, d) {
                            // Use namespaced event to avoid conflicts
                            if (event.sourceEvent.type === 'touchstart') {
                                selectNode(event.sourceEvent, d, this);
                            }
                        })
                        .on("end.highlight", function (event, d) {
                            if (event.sourceEvent.type === 'touchend') {
                                deselectNode(event.sourceEvent, d, this);
                            }
                        })
                );


            // Node event handlers
            function selectNode(_event: MouseEvent, d: NodeData, nodeElement: SVGCircleElement): void {
                highlightNeighbors(_event, d, nodeElement);
                fillTooltip(
                    d,
                    incomingCount[d.playlist_id],
                    outgoingCount[d.playlist_id]
                );
            }

            function deselectNode(_event: MouseEvent, d: NodeData, nodeElement: SVGCircleElement): void {
                d3.selectAll("circle").attr("opacity", 1);
                d3.selectAll("line").attr("opacity", (d) =>
                    linkOpacity(d as ProcessedEdgeData)
                );
                d3.select("#graph-info-panel").style("display", "none");
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

            // Add slider event listeners
            const linkDistanceSlider = document.getElementById("link-distance") as HTMLInputElement;
            const linkStrengthSlider = document.getElementById("link-strength") as HTMLInputElement;
            const chargeStrengthSlider = document.getElementById("charge-strength") as HTMLInputElement;
            const centerForceSlider = document.getElementById("center-force") as HTMLInputElement;
            const collisionForceSlider = document.getElementById("collision-force") as HTMLInputElement;
            const nodeSizeSlider = document.getElementById("node-size") as HTMLInputElement;
            const lineWidthSlider = document.getElementById("line-width") as HTMLInputElement;
            
            if (linkDistanceSlider) {
                linkDistanceSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("link-distance-value")!.textContent = value.toString();
                    linkForce.distance(value);
                    saveForceSettings({ linkDistance: value });
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (linkStrengthSlider) {
                linkStrengthSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("link-strength-value")!.textContent = value.toFixed(2);
                    linkForce.strength(value);
                    saveForceSettings({ linkStrength: value });
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (chargeStrengthSlider) {
                chargeStrengthSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("charge-strength-value")!.textContent = value.toString();
                    chargeForce.strength(value);
                    saveForceSettings({ chargeStrength: value });
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (centerForceSlider) {
                centerForceSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("center-force-value")!.textContent = value.toFixed(2);
                    xForce.strength(value);
                    yForce.strength(value);
                    saveForceSettings({ centerForce: value });
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (collisionForceSlider) {
                collisionForceSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("collision-force-value")!.textContent = value.toFixed(1);
                    collisionForce.strength(value);
                    saveForceSettings({ collisionForce: value });
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (nodeSizeSlider) {
                nodeSizeSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("node-size-value")!.textContent = value.toFixed(1);

                    // Update the settings object in scope
                    settings.nodeSize = value;
                    saveForceSettings({ nodeSize: value });
                    
                    // Update node sizes
                    node.transition()
                        .duration(300)
                        .attr("r", (d: NodeData) => {
                            const baseSize = value;
                            return baseSize + Math.sqrt(outgoingCount[d.playlist_id] || 1) * 4;
                        });
                    
                    // Update collision force radius
                    collisionForce.radius((d: NodeData) => {
                        const baseSize = value;
                        return baseSize + Math.sqrt(outgoingCount[d.playlist_id] || 1) * 4 + 3;
                    });
                    
                    simulation.alpha(0.3).restart();
                });
            }
            
            if (lineWidthSlider) {
                lineWidthSlider.addEventListener("input", function() {
                    const value = +this.value;
                    document.getElementById("line-width-value")!.textContent = value.toFixed(1);
                    saveForceSettings({ lineWidth: value });
                    
                    // Update line widths
                    link.transition()
                        .duration(300)
                        .attr("stroke-width", value);
                });
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