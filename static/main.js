// API configuration
const API_BASE_URL = 'http://localhost:5000/api';

async function searchAPI(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query, top_k: 20 })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Search API error:', error);
        throw error;
    }
}

function loadDataAndRender(query) {
    // Show loading state
    const svg = d3.select("#bubbleChart");
    svg.selectAll("*").remove();
    
    const width = +svg.attr("width");
    const height = +svg.attr("height");
    
    // Add loading indicator
    const loadingText = svg.append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .attr("font-size", "18px")
        .attr("fill", "#666")
        .attr("class", "loading")
        .text("Searching...");

    // Perform API search and return the promise
    return searchAPI(query).then(data => {
        // Remove loading indicator
        loadingText.remove();
        
        if (!data || data.length === 0) {
            svg.append("text")
                .attr("x", width / 2)
                .attr("y", height / 2)
                .attr("text-anchor", "middle")
                .attr("font-size", "18px")
                .attr("fill", "#666")
                .text("No results found for your query.");
            return;
        }

        renderBubbleChart(data);
    }).catch(error => {
        // Remove loading indicator
        loadingText.remove();
        
        // Show error message
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2)
            .attr("text-anchor", "middle")
            .attr("font-size", "18px")
            .attr("fill", "#d32f2f")
            .text("Error loading search results. Please try again.");
            
        console.error('Failed to load search results:', error);
        throw error; // Re-throw to handle in calling function
    });
}

function renderBubbleChart(data) {
    const svg = d3.select("#bubbleChart");
    const width = +svg.attr("width");
    const height = +svg.attr("height");

    svg.selectAll("*").remove();

    // Use domain-based topics
    data.forEach(d => {
        d.primaryTopic = d.topic || d.primaryTopic || 'unknown';
        d.topics = d.topics || [d.primaryTopic];
        d.secondaryTopics = [];
    });

    // Group by primary topic (domain)
    const topics = d3.group(data, d => d.primaryTopic);
    const clusters = Array.from(topics, ([topic, docs]) => ({
        topic,
        docs,
        count: docs.length,
        totalScore: d3.sum(docs, d => d.score),
        avgScore: d3.mean(docs, d => d.score)
    }));

    // Create a more diverse color scale for domains
    const color = d3.scaleOrdinal()
        .domain(clusters.map(d => d.topic))
        .range([
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
        ]);

    // Improve radius scaling for better visualization
    const docRadiusScale = d3.scaleSqrt()
        .domain(d3.extent(data, d => d.score))
        .range([8, 35]);

    const clusterRadiusScale = d3.scaleSqrt()
        .domain(d3.extent(clusters, d => d.count))
        .range([40, 100]);

    // Position clusters with better spacing
    const clusterSimulation = d3.forceSimulation(clusters)
        .force("charge", d3.forceManyBody().strength(20))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(d => clusterRadiusScale(d.count) + 20))
        .on("tick", ticked);

    // Run simulation longer for better positioning
    setTimeout(() => {
        clusterSimulation.stop();

        // Fix cluster centers
        clusters.forEach(d => {
            d.fx = d.x;
            d.fy = d.y;
            d.radius = clusterRadiusScale(d.count);
        });

        // Map topic names to cluster centers
        const clusterCenterMap = Object.fromEntries(clusters.map(c => [c.topic, c]));

        // Position documents within clusters
        const docSim = d3.forceSimulation(data)
            .force("x", d3.forceX(d => clusterCenterMap[d.primaryTopic]?.x).strength(0.8))
            .force("y", d3.forceY(d => clusterCenterMap[d.primaryTopic]?.y).strength(0.8))
            .force("collision", d3.forceCollide().radius(d => docRadiusScale(d.score) + 2))
            .force("charge", d3.forceManyBody().strength(-5))
            .on("tick", ticked);
    }, 300);

    // Draw cluster backgrounds
    const clusterBackgrounds = svg.selectAll(".cluster-bg")
        .data(clusters)
        .enter().append("circle")
        .attr("class", "cluster-bg")
        .attr("r", d => clusterRadiusScale(d.count))
        .attr("fill", d => color(d.topic))
        .attr("fill-opacity", 0.1)
        .attr("stroke", d => color(d.topic))
        .attr("stroke-width", 2)
        .attr("stroke-opacity", 0.3);

    // Draw cluster labels
    const clusterGroups = svg.selectAll(".cluster")
        .data(clusters)
        .enter().append("g")
        .attr("class", "cluster");

    clusterGroups.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".3em")
        .style("font-weight", "bold")
        .style("font-size", d => Math.min(14, clusterRadiusScale(d.count) / 4) + "px")
        .style("pointer-events", "none")
        .text(d => d.topic.toUpperCase())
        .attr("fill", d => color(d.topic));

    // Add count labels
    clusterGroups.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", "1.5em")
        .style("font-size", "10px")
        .style("pointer-events", "none")
        .text(d => `(${d.count} docs)`)
        .attr("fill", "#666");

    // Draw document nodes
    const node = svg.selectAll("circle.doc-node")
        .data(data)
        .enter().append("circle")
        .attr("class", "doc-node")
        .attr("r", d => docRadiusScale(d.score))
        .attr("fill", d => color(d.primaryTopic))
        .attr("fill-opacity", 0.7)
        .attr("stroke", "#fff")
        .attr("stroke-width", 2)
        .style("cursor", "pointer")
        .on("mouseover", (event, d) => {
            // Highlight the node
            d3.select(event.target)
                .attr("stroke", "#333")
                .attr("stroke-width", 3);
            
            tooltip.style("visibility", "visible")
                .html(`
                    <strong>${d.title}</strong><br/>
                    <em>Domain: ${d.primaryTopic}</em><br/>
                    Score: ${d.score.toFixed(3)}<br/>
                    ${d.snippet}<br/>
                    <a href="${d.url}" target="_blank">Visit →</a>
                `);
        })
        .on("mousemove", event => {
            tooltip.style("top", (event.pageY - 10) + "px")
                .style("left", (event.pageX + 10) + "px");
        })
        .on("mouseout", (event) => {
            // Reset node styling
            d3.select(event.target)
                .attr("stroke", "#fff")
                .attr("stroke-width", 2);
            
            tooltip.style("visibility", "hidden");
        })
        .on("click", (event, d) => window.open(d.url, "_blank"));

    // Create tooltip
    const tooltip = d3.select("body").append("div")
        .attr("class", "tooltip")
        .style("position", "absolute")
        .style("visibility", "hidden")
        .style("background", "rgba(0, 0, 0, 0.8)")
        .style("color", "white")
        .style("padding", "10px")
        .style("border-radius", "5px")
        .style("font-size", "12px")
        .style("max-width", "300px")
        .style("z-index", "1000");

    function ticked() {
        clusterBackgrounds
            .attr("cx", d => d.x)
            .attr("cy", d => d.y);
        
        node.attr("cx", d => d.x).attr("cy", d => d.y);
        
        clusterGroups.attr("transform", d => `translate(${d.x},${d.y})`);
    }
}


// Search functionality
function performSearch() {
    const queryInput = document.getElementById("queryInput");
    const searchBtn = document.getElementById("searchBtn");
    const query = queryInput.value.trim();
    
    if (!query) {
        alert("Please enter a search query");
        return;
    }

    console.log("Search query submitted:", query);

    // Disable search while processing
    searchBtn.disabled = true;
    searchBtn.textContent = "Searching...";
    queryInput.disabled = true;

    const header = document.getElementById("header");
    const results = document.getElementById("results");

    // Remove centered class after first submission
    header.classList.remove("centered");
    results.style.display = "block";

    // Load & visualize
    loadDataAndRender(query).finally(() => {
        // Re-enable search
        searchBtn.disabled = false;
        searchBtn.textContent = "Search";
        queryInput.disabled = false;
    });
}

// Event listeners
document.getElementById("queryInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        performSearch();
    }
});

document.getElementById("searchBtn").addEventListener("click", performSearch);





function exportResultsToText(data) {
  // Group by query_id and sort each group by score descending
  const grouped = d3.groups(data, d => d.query_id);

  let lines = [];

  grouped.forEach(([query_id, results]) => {
    results
      .sort((a, b) => d3.descending(a.score, b.score))
      .forEach((d, i) => {
        const rank = i + 1;
        lines.push(`${query_id}\t${rank}\t${d.url}\t${d.score.toFixed(3)}`);
      });
  });

  const fileContent = lines.join("\n");
  const blob = new Blob([fileContent], { type: "text/plain;charset=utf-8" });

  // Trigger file download
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "search_results.txt";
  a.click();
  URL.revokeObjectURL(a.href); // Clean up
}
