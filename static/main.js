// API configuration
const API_BASE_URL = 'http://localhost:5000/api';

async function searchAPI(query) {
    try {
        console.log(`Making API call to: ${API_BASE_URL}/search`);
        console.log(`Query: ${query}`);
        
        const response = await fetch(`${API_BASE_URL}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });

        console.log(`Response status: ${response.status}`);
        console.log(`Response headers:`, Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log('API response data structure:', {
            type: typeof data,
            hasDocuments: data.documents ? true : false,
            hasLLMResponse: data.llm_response ? true : false,
            documentsLength: data.documents ? data.documents.length : "N/A",
            sample: data.documents && data.documents.length > 0 ? data.documents[0] : "No data",
            llm_response: data.llm_response || "N/A"
        });
        
        if (data.documents && Array.isArray(data.documents)) {
            window.currentLLMResponse = data.llm_response || '';
            return data.documents;
        } else if (Array.isArray(data)) {
            // If the API returns a simple array of documents and no LLM response
            return data;
        } else {
            console.error('API did not return valid format:', data);
            throw new Error(`API returned invalid format`);
        }
    } catch (error) {
        console.error('Search API error details:', {
            message: error.message,
            stack: error.stack,
            name: error.name,
            query: query
        });
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
            const svg = d3.select("#bubbleChart");
            const canvasWidth = window.innerWidth * 0.8;
            const canvasHeight = window.innerHeight * 0.8;
            svg.attr("width", canvasWidth).attr("height", canvasHeight);
            
            svg.append("text")
                .attr("x", canvasWidth / 2)
                .attr("y", canvasHeight / 2)
                .attr("text-anchor", "middle")
                .attr("font-size", "18px")
                .attr("fill", "#666")
                .text("No results found for your query.");
            return;
        }

        // Store data globally and show controls
        currentData = data;
        document.getElementById("controls").style.display = "block";

        if (isListView) {
            renderListView(data);
        } else {
            renderBubbleChart(data);
        }
    }).catch(error => {
        // Remove loading indicator
        loadingText.remove();
        
        console.error('Failed to load search results:', {
            message: error.message,
            stack: error.stack,
            name: error.name
        });
        
        // Show error message
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2)
            .attr("text-anchor", "middle")
            .attr("font-size", "18px")
            .attr("fill", "#d32f2f")
            .text(`Error: ${error.message}`);
            
        // Add a secondary line with suggestion
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2 + 30)
            .attr("text-anchor", "middle")
            .attr("font-size", "14px")
            .attr("fill", "#666")
            .text("Please check if the search API is running and try again.");
            
        throw error; // Re-throw to handle in calling function
    });
}

function renderBubbleChart(data) {
    console.log("=== BUBBLE CHART DEBUG ===");
    console.log("Input data:", data);
    console.log("Data type:", Array.isArray(data) ? "array" : typeof data);
    console.log("Data length:", Array.isArray(data) ? data.length : "N/A");
    
    if (!Array.isArray(data) || data.length === 0) {
        console.error("Invalid data for bubble chart:", data);
        const svg = d3.select("#bubbleChart");
        svg.selectAll("*").remove();
        svg.append("text")
            .attr("x", "50%")
            .attr("y", "50%")
            .attr("text-anchor", "middle")
            .attr("font-size", "18px")
            .attr("fill", "#d32f2f")
            .text("No data available for bubble chart");
        return;
    }
    
    const svg = d3.select("#bubbleChart");
    
    // Set fixed canvas size to 80% of screen
    const canvasWidth = window.innerWidth * 0.8;
    const canvasHeight = window.innerHeight * 0.8;
    
    svg.attr("width", canvasWidth).attr("height", canvasHeight);
    svg.selectAll("*").remove();

    console.log("Rendering bubble chart with data:", data);
    console.log("Number of results:", data.length);
    console.log(`Canvas dimensions: ${canvasWidth}x${canvasHeight}`);

    // Create a larger virtual space for the visualization
    const virtualWidth = canvasWidth * 2;
    const virtualHeight = canvasHeight * 2;

    // Add zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => {
            mainGroup.attr("transform", event.transform);
        });

    svg.call(zoom);

    // Create main group that will be transformed
    const mainGroup = svg.append("g")
        .attr("class", "main-group");

    // Add subtle grid background for better orientation
    const gridGroup = mainGroup.append("g")
        .attr("class", "grid");

    const gridSize = 100;
    const gridLines = [];

    // Vertical lines
    for (let x = 0; x <= virtualWidth; x += gridSize) {
        gridGroup.append("line")
            .attr("x1", x)
            .attr("y1", 0)
            .attr("x2", x)
            .attr("y2", virtualHeight)
            .attr("stroke", "#e0e0e0")
            .attr("stroke-width", 0.5)
            .attr("opacity", 0.3);
    }

    // Horizontal lines
    for (let y = 0; y <= virtualHeight; y += gridSize) {
        gridGroup.append("line")
            .attr("x1", 0)
            .attr("y1", y)
            .attr("x2", virtualWidth)
            .attr("y2", y)
            .attr("stroke", "#e0e0e0")
            .attr("stroke-width", 0.5)
            .attr("opacity", 0.3);
    }

    // Add background for better zoom/pan experience
    svg.insert("rect", ":first-child")
        .attr("width", "100%")
        .attr("height", "100%")
        .attr("fill", "#fafafa")
        .style("cursor", "grab")
        .style("cursor", "-webkit-grab")
        .on("mousedown", function() {
            d3.select(this).style("cursor", "grabbing")
                .style("cursor", "-webkit-grabbing");
        })
        .on("mouseup", function() {
            d3.select(this).style("cursor", "grab")
                .style("cursor", "-webkit-grab");
        });

    // Parse topics into arrays and identify primary/secondary
    data.forEach(d => {
        if (typeof d.topic === 'string') {
            d.topics = d.topic.split(",").map(t => t.trim());
        } else if (Array.isArray(d.topics)) {
            // Already parsed
        } else {
            d.topics = ['general'];
        }
        d.primaryTopic = d.topics[0];
        d.secondaryTopics = d.topics.slice(1);
    });

    // Group by primary topic
    const topics = d3.group(data, d => d.primaryTopic);
    const clusters = Array.from(topics, ([topic, docs]) => ({
        topic,
        docs,
        count: docs.length,
        totalScore: d3.sum(docs, d => d.raw_score), // Use raw_score instead of normalized score
        avgScore: d3.mean(docs, d => d.raw_score),  // Use raw_score for average too
        totalNormalizedScore: d3.sum(docs, d => d.score) // Keep normalized for other purposes
    }));

    console.log("Topics found:", Array.from(topics.keys()));
    console.log("Clusters:", clusters);

    // Handle case where no clusters are found
    if (clusters.length === 0) {
        console.error("No clusters found in data");
        svg.append("text")
            .attr("x", canvasWidth / 2)
            .attr("y", canvasHeight / 2)
            .attr("text-anchor", "middle")
            .attr("font-size", "18px")
            .attr("fill", "#666")
            .text("No valid clusters found in search results.");
        return;
    }

    const color = d3.scaleOrdinal(d3.schemeCategory10);

    const docRadiusScale = d3.scaleLinear()
        .domain(d3.extent(data, d => d.score))
        .range([18, 50]); // Increased minimum size for better visibility

    const clusterRadiusScale = d3.scaleSqrt()
        .domain([0, d3.max(clusters, d => d.totalScore)])
        .range([60, 140]); // Increased cluster radius range

    // Position clusters using a more spread out approach in virtual space
    const numClusters = clusters.length;
    const centerX = virtualWidth / 2;
    const centerY = virtualHeight / 2;
    
    // Sort clusters by total score (descending) to identify the top cluster
    const sortedClusters = [...clusters].sort((a, b) => b.totalScore - a.totalScore);
    const topCluster = sortedClusters[0];
    const otherClusters = sortedClusters.slice(1);
    
    console.log("Top cluster (will be centered):", topCluster.topic, "Score:", topCluster.totalScore);
    
    // Always place the top scoring cluster in the center
    topCluster.x = centerX;
    topCluster.y = centerY;
    
    // Position other clusters around the center cluster
    if (otherClusters.length === 0) {
        // Only one cluster - already positioned in center
    } else if (otherClusters.length === 1) {
        // One additional cluster - place it to the right of center
        otherClusters[0].x = centerX + virtualWidth * 0.15;
        otherClusters[0].y = centerY;
    } else if (otherClusters.length === 2) {
        // Two additional clusters - place them left and right
        otherClusters[0].x = centerX - virtualWidth * 0.15;
        otherClusters[0].y = centerY;
        otherClusters[1].x = centerX + virtualWidth * 0.15;
        otherClusters[1].y = centerY;
    } else if (otherClusters.length === 3) {
        // Three additional clusters - triangular arrangement around center
        const positions = [
            [centerX, centerY - virtualHeight * 0.15],        // top
            [centerX - virtualWidth * 0.13, centerY + virtualHeight * 0.1],  // bottom-left
            [centerX + virtualWidth * 0.13, centerY + virtualHeight * 0.1]   // bottom-right
        ];
        otherClusters.forEach((cluster, i) => {
            cluster.x = positions[i][0];
            cluster.y = positions[i][1];
        });
    } else {
        // Four or more additional clusters - circular arrangement around center
        const angleStep = (2 * Math.PI) / otherClusters.length;
        const clusterDistance = Math.min(virtualWidth, virtualHeight) * 0.12; // Tight circle around center
        
        otherClusters.forEach((cluster, i) => {
            const angle = i * angleStep;
            cluster.x = centerX + Math.cos(angle) * clusterDistance;
            cluster.y = centerY + Math.sin(angle) * clusterDistance;
        });
    }
    
    // Fix cluster positions and set radius
    clusters.forEach(cluster => {
        cluster.fx = cluster.x;
        cluster.fy = cluster.y;
        cluster.radius = clusterRadiusScale(cluster.totalScore);
    });

    console.log("Cluster positions:", clusters.map(c => ({topic: c.topic, x: c.x, y: c.y})));

    // Calculate better initial positioning based on content bounds
    let contentBounds, initialTransform;
    try {
        contentBounds = {
            minX: Math.min(...clusters.map(c => c.x)) - 100,
            maxX: Math.max(...clusters.map(c => c.x)) + 100,
            minY: Math.min(...clusters.map(c => c.y)) - 100,
            maxY: Math.max(...clusters.map(c => c.y)) + 100
        };
        
        console.log("Content bounds calculated:", contentBounds);
        
        const contentWidth = contentBounds.maxX - contentBounds.minX;
        const contentHeight = contentBounds.maxY - contentBounds.minY;
        
        // Calculate scale to fit content in canvas with some padding
        const scaleX = (canvasWidth * 0.6) / contentWidth; // Reduced from 0.8 for more zoom
        const scaleY = (canvasHeight * 0.6) / contentHeight; // Reduced from 0.8 for more zoom
        const optimalScale = Math.min(scaleX, scaleY, 1.2); // Increased from 0.8 for better readability
        
        // Center the content
        const contentCenterX = (contentBounds.minX + contentBounds.maxX) / 2;
        const contentCenterY = (contentBounds.minY + contentBounds.maxY) / 2;
        
        const translateX = canvasWidth / 2 - contentCenterX * optimalScale;
        const translateY = canvasHeight / 2 - contentCenterY * optimalScale;

        // Reset zoom to fit content initially - show all clusters at once
        initialTransform = d3.zoomIdentity
            .translate(translateX, translateY)
            .scale(optimalScale);
            
        console.log("Initial transform calculated:", initialTransform);
    } catch (error) {
        console.error("Error calculating content bounds:", error, "Clusters:", clusters);
        // Fallback to center positioning with better zoom
        initialTransform = d3.zoomIdentity
            .translate(canvasWidth * 0.25, canvasHeight * 0.25)
            .scale(1.0); // Increased from 0.6 for better default view
        console.log("Using fallback transform:", initialTransform);
    }
    
    svg.call(zoom.transform, initialTransform);

    // Map topic names to cluster centers
    const clusterCenterMap = Object.fromEntries(clusters.map(c => [c.topic, c]));

    // Position documents around their cluster centers with improved force simulation
    const docSim = d3.forceSimulation(data)
        .force("x", d3.forceX(d => clusterCenterMap[d.primaryTopic]?.x || centerX).strength(0.3))
        .force("y", d3.forceY(d => clusterCenterMap[d.primaryTopic]?.y || centerY).strength(0.3))
        .force("collision", d3.forceCollide().radius(d => Math.max(18, docRadiusScale(d.score)) + 6).strength(0.9))
        .force("charge", d3.forceManyBody().strength(-80))
        .alphaDecay(0.01) // Slower decay for better settling
        .velocityDecay(0.2) // Less velocity decay
        .on("tick", ticked);
    
    // Add custom force to keep nodes within cluster bounds
    docSim.force("cluster", () => {
        data.forEach(d => {
            const cluster = clusterCenterMap[d.primaryTopic];
            if (cluster) {
                const dx = d.x - cluster.x;
                const dy = d.y - cluster.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const maxDistance = cluster.radius + 50; // Allow some spread beyond cluster circle
                
                if (distance > maxDistance) {
                    const scale = maxDistance / distance;
                    d.x = cluster.x + dx * scale;
                    d.y = cluster.y + dy * scale;
                }
            }
        });
    });

    const clusterGroups = mainGroup.selectAll(".cluster")
        .data(clusters)
        .enter().append("g")
        .attr("class", "cluster")
        .attr("transform", d => `translate(${d.x},${d.y})`);

    // Add background circles for cluster labels with better sizing
    clusterGroups.append("circle")
        .attr("r", d => Math.max(40, clusterRadiusScale(d.totalScore) * 0.8))
        .attr("fill", d => color(d.topic))
        .attr("fill-opacity", 0.08)
        .attr("stroke", d => color(d.topic))
        .attr("stroke-width", 3)
        .attr("stroke-opacity", 0.4)
        .attr("stroke-dasharray", "5,5");

    clusterGroups.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".3em")
        .style("font-weight", "bold")
        .style("font-size", "16px")
        .style("pointer-events", "none")
        .text(d => d.topic.toUpperCase())
        .attr("fill", d => color(d.topic))
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .attr("paint-order", "stroke");

    const nodeGroups = mainGroup.selectAll(".doc-node-group")
        .data(data)
        .enter().append("g")
        .attr("class", "doc-node-group");

    const node = nodeGroups.append("circle")
        .attr("class", "doc-node")
        .attr("r", d => Math.max(18, docRadiusScale(d.score)))
        .attr("fill", d => color(d.primaryTopic))
        .attr("fill-opacity", 0.8)
        .attr("stroke", "#333")
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.9);

    // Add titles inside bubbles for larger ones
    const nodeText = nodeGroups.append("text")
        .attr("class", "doc-node-text")
        .attr("text-anchor", "middle")
        .attr("dy", "0.3em")
        .attr("font-size", d => Math.min(14, Math.max(10, docRadiusScale(d.score) / 3.5)))
        .attr("fill", "#333")
        .attr("pointer-events", "none")
        .style("font-weight", "600")
        .text(d => {
            const radius = Math.max(18, docRadiusScale(d.score));
            const maxLength = Math.floor(radius / 3.5);
            return d.title.length > maxLength ? d.title.substring(0, maxLength) + "..." : d.title;
        })
        .style("display", d => docRadiusScale(d.score) > 25 ? "block" : "none");

    // Add event listeners to the group to prevent flickering
    nodeGroups
        .on("mouseover", (event, d) => {
            d3.select(event.currentTarget).select("circle")
                .transition().duration(150)
                .attr("fill-opacity", 0.9)
                .attr("stroke-width", 2.5);
            
            tooltip.style("visibility", "visible")
            .html(`<strong>${d.title}</strong><br/><em>Score: ${d.score.toFixed(3)} | Rank: ${d.rank}</em><br/>${d.snippet.substring(0, 200)}...<br/><a href="${d.url}" target="_blank">Visit Page</a>`);
        })
        .on("mousemove", event => {
            tooltip.style("top", (event.pageY - 10) + "px")
            .style("left", (event.pageX + 10) + "px");
        })
        .on("mouseout", (event, d) => {
            d3.select(event.currentTarget).select("circle")
                .transition().duration(150)
                .attr("fill-opacity", 0.7)
                .attr("stroke-width", 1.5);
            
            tooltip.style("visibility", "hidden");
        })
        .on("click", (event, d) => window.open(d.url, "_blank"))
        .style("cursor", "pointer");

    // const topDocs = Array.from(d3.group(data, d => d.primaryTopic), ([topic, docs]) =>
    //     docs.sort((a, b) => d3.descending(a.score, b.score)).slice(0, 2)
    //     ).flat();

    // const labels = mainGroup.selectAll(".doc-label")
    //     .data(topDocs)
    //     .enter()
    //     .append("text")
    //     .attr("class", "doc-label")
    //     .attr("text-anchor", "middle")
    //     .attr("font-size", "12px")
    //     .attr("fill", "#333")
    //     .text(d => d.title);

    // Remove any existing tooltips before creating a new one
    d3.selectAll(".tooltip").remove();
    const tooltip = d3.select("body").append("div")
        .attr("class", "tooltip");

    // Add zoom controls
    const controls = svg.append("g")
        .attr("class", "zoom-controls")
        .attr("transform", `translate(${canvasWidth - 80}, 20)`);

    const controlsBackground = controls.append("rect")
        .attr("width", 60)
        .attr("height", 130)
        .attr("fill", "white")
        .attr("stroke", "#ccc")
        .attr("stroke-width", 1)
        .attr("rx", 5);

    const zoomInBtn = controls.append("g")
        .attr("class", "zoom-btn")
        .attr("transform", "translate(10, 10)")
        .style("cursor", "pointer");

    zoomInBtn.append("rect")
        .attr("width", 40)
        .attr("height", 25)
        .attr("fill", "#007acc")
        .attr("rx", 3);

    zoomInBtn.append("text")
        .attr("x", 20)
        .attr("y", 17)
        .attr("text-anchor", "middle")
        .attr("fill", "white")
        .attr("font-size", "16px")
        .attr("font-weight", "bold")
        .text("+");

    const zoomOutBtn = controls.append("g")
        .attr("class", "zoom-btn")
        .attr("transform", "translate(10, 45)")
        .style("cursor", "pointer");

    zoomOutBtn.append("rect")
        .attr("width", 40)
        .attr("height", 25)
        .attr("fill", "#007acc")
        .attr("rx", 3);

    zoomOutBtn.append("text")
        .attr("x", 20)
        .attr("y", 17)
        .attr("text-anchor", "middle")
        .attr("fill", "white")
        .attr("font-size", "16px")
        .attr("font-weight", "bold")
        .text("−");

    const resetBtn = controls.append("g")
        .attr("class", "zoom-btn")
        .attr("transform", "translate(10, 75)")
        .style("cursor", "pointer");

    resetBtn.append("rect")
        .attr("width", 40)
        .attr("height", 20)
        .attr("fill", "#28a745")
        .attr("rx", 3);

    resetBtn.append("text")
        .attr("x", 20)
        .attr("y", 14)
        .attr("text-anchor", "middle")
        .attr("fill", "white")
        .attr("font-size", "9px")
        .text("Default");

    const overviewBtn = controls.append("g")
        .attr("class", "zoom-btn")
        .attr("transform", "translate(10, 105)")
        .style("cursor", "pointer");

    overviewBtn.append("rect")
        .attr("width", 40)
        .attr("height", 20)
        .attr("fill", "#6c757d")
        .attr("rx", 3);

    overviewBtn.append("text")
        .attr("x", 20)
        .attr("y", 14)
        .attr("text-anchor", "middle")
        .attr("fill", "white")
        .attr("font-size", "8px")
        .text("Zoom Out");

    // Add zoom control functionality
    zoomInBtn.on("click", () => {
        svg.transition().duration(300).call(
            zoom.scaleBy, 1.5
        );
    });

    zoomOutBtn.on("click", () => {
        svg.transition().duration(300).call(
            zoom.scaleBy, 1 / 1.5
        );
    });

    resetBtn.on("click", () => {
        svg.transition().duration(500).call(
            zoom.transform, initialTransform
        );
    });

    overviewBtn.on("click", () => {
        // Zoom out to see everything but keep it readable
        // Use the same calculation as initial but with more padding
        const overviewScale = Math.min(optimalScale * 0.7, 0.5); // 70% of optimal scale
        const overviewTranslateX = canvasWidth / 2 - contentCenterX * overviewScale;
        const overviewTranslateY = canvasHeight / 2 - contentCenterY * overviewScale;
        
        const overviewTransform = d3.zoomIdentity
            .translate(overviewTranslateX, overviewTranslateY)
            .scale(overviewScale);
        svg.transition().duration(500).call(
            zoom.transform, overviewTransform
        );
    });

    function ticked() {
        nodeGroups.attr("transform", d => `translate(${d.x},${d.y})`);
        
        // Update label positions for top documents
        // labels
        //     .attr("x", d => d.x)
        //     .attr("y", d => d.y - Math.max(18, docRadiusScale(d.score)) - 12);
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

document.getElementById("toggleView").addEventListener("click", toggleView);

// Handle window resize for responsive bubble chart
window.addEventListener("resize", () => {
    if (currentData && !isListView) {
        renderBubbleChart(currentData);
    }
});

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

function renderListView(data) {
    const resultsContainer = document.getElementById("searchResults");
    resultsContainer.innerHTML = "";
    
    data.forEach((result, index) => {
        const resultItem = document.createElement("div");
        resultItem.className = "search-result-item";
        
        resultItem.innerHTML = `
            <div class="result-title">
                <a href="${result.url}" target="_blank">${result.title}</a>
            </div>
            <div class="result-url">${result.url}</div>
            <div class="result-snippet">${result.snippet}</div>
            <div class="result-score">
                Score: ${result.score.toFixed(3)} | Rank: ${result.rank}
                <span class="result-topic">${result.topic}</span>
            </div>
        `;
        
        resultsContainer.appendChild(resultItem);
    });
}

let currentData = null;
let isListView = false;

function toggleView() {
    const bubbleView = document.getElementById("bubbleView");
    const listView = document.getElementById("listView");
    const toggleBtn = document.getElementById("toggleView");
    
    if (isListView) {
        // Switch to bubble view
        bubbleView.style.display = "block";
        listView.style.display = "none";
        toggleBtn.textContent = "Switch to List View";
        isListView = false;
        
        if (currentData) {
            renderBubbleChart(currentData);
        }
    } else {
        // Switch to list view
        bubbleView.style.display = "none";
        listView.style.display = "block";
        toggleBtn.textContent = "Switch to Bubble View";
        isListView = true;
        
        if (currentData) {
            renderListView(currentData);
        }
    }
}
