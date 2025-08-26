import * as d3 from 'd3';

interface NodeData extends d3.SimulationNodeDatum {
    id: string;
    playlist_id: string;
    name: string;
    size: number;
    color: string;
    time_period: 'old' | 'new' | 'both';
}

interface EdgeData {
    playlist_id_1: string;
    playlist_id_2: string;
    weight: number;
}

interface ProcessedEdgeData extends d3.SimulationLinkDatum<NodeData> {
    source: string | NodeData;
    target: string | NodeData;
    weight: number;
}

// Color scheme for time periods
const COLOR_MAP: Record<string, string> = {
    old: "#3b82f6",   // blue for old dataset only
    new: "#10b981",   // green for new dataset only
    both: "#8b5cf6",  // purple for nodes in both periods
};

function createCombinedGraph(jobId: string): void {
    const container = document.getElementById("graph-container");
    if (!container) {
        console.error("Graph container not found");
        return;
    }
    
    const width = container.offsetWidth;
    const height = container.offsetHeight;

    // Clear loading state
    container.innerHTML = "";

    // Create SVG with proper types
    const svg = d3
        .select<HTMLElement, unknown>("#graph-container")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    // Create groups for zoom behavior
    const g = svg.append("g");

    // Load combined graph data (d3.csv returns DSVRowString by default)
    Promise.all([
        d3.csv(`/first/combine/data/${jobId}/nodes`),
        d3.csv(`/first/combine/data/${jobId}/edges`),
    ])
        .then(([nodes, edges]) => {
            // Process nodes with proper typing
            const processedNodes: NodeData[] = nodes.map((d) => ({
                id: d.playlist_id || '',
                playlist_id: d.playlist_id || '',
                name: d.playlist_id || '',
                size: 10,
                x: Math.random() * width,
                y: Math.random() * height,
                color: COLOR_MAP[d.time_period as string] || "#6b7280",
                time_period: (d.time_period || 'both') as 'old' | 'new' | 'both',
            }));

            // Process edges with proper typing
            const processedEdges: ProcessedEdgeData[] = edges.map((d) => ({
                source: d.playlist_id_1 || '',
                target: d.playlist_id_2 || '',
                weight: +(d.weight || 1),
            }));

            // Create force simulation with proper types
            const simulation = d3
                .forceSimulation<NodeData>(processedNodes)
                .force(
                    "link",
                    d3
                        .forceLink<NodeData, ProcessedEdgeData>(processedEdges)
                        .id((d: NodeData) => d.id)
                        .distance(50)
                )
                .force("charge", d3.forceManyBody().strength(-100))
                .force("center", d3.forceCenter(width / 2, height / 2));

            // Create zoom behavior with proper types
            const zoom = d3
                .zoom<SVGSVGElement, unknown>()
                .scaleExtent([0.1, 3])
                .on("zoom", (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) =>
                    g.attr("transform", event.transform.toString())
                );

            svg.call(zoom);

            // Create edges with proper types
            const link = g
                .append("g")
                .selectAll<SVGLineElement, ProcessedEdgeData>("line")
                .data(processedEdges)
                .enter()
                .append("line")
                .attr("stroke", "#999")
                .attr("stroke-opacity", 0.6)
                .attr("stroke-width", (d: ProcessedEdgeData) => Math.sqrt(d.weight));

            // Create nodes with proper types
            const node = g
                .append("g")
                .selectAll<SVGCircleElement, NodeData>("circle")
                .data(processedNodes)
                .enter()
                .append("circle")
                .attr("r", (d: NodeData) => Math.sqrt(d.size) * 3)
                .attr("fill", (d: NodeData) => d.color)
                .attr("stroke", "#fff")
                .attr("stroke-width", 1.5)
                .call(
                    d3
                        .drag<SVGCircleElement, NodeData>()
                        .on("start", dragstarted)
                        .on("drag", dragged)
                        .on("end", dragended)
                );

            // Add tooltips with proper types
            node.append("title").text(
                (d: NodeData) => `Playlist: ${d.playlist_id}\nTime Period: ${d.time_period}`
            );

            // Update positions with proper types
            simulation.on("tick", () => {
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
            });

            function dragstarted(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }

            function dragged(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData) {
                d.fx = event.x;
                d.fy = event.y;
            }

            function dragended(event: d3.D3DragEvent<SVGCircleElement, NodeData, NodeData>, d: NodeData) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        })
        .catch((error) => {
            console.error("Error loading graph data:", error);
            container.innerHTML = '<div class="text-error text-center">Error loading graph data</div>';
        });
}

// Make the function available globally
(window as any).createCombinedGraph = createCombinedGraph;