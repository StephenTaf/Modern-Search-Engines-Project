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

             // Clear LLM response if there's no result
            document.getElementById("llm-response-text").textContent = "No AI answer available.";
            return;
        }

        const llmResponseBox = document.getElementById("llm-response-text");
        if (window.currentLLMResponse) {
            llmResponseBox.innerHTML = formatLLMResponse(window.currentLLMResponse);
        } else {
            llmResponseBox.textContent = "No AI answer available.";
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
    console.log("Data:", data);
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
            .attr("stroke", "#d7d7d7ff")
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
            .attr("stroke", "#d7d7d7ff")
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


    // Group by domain
    const domains = d3.group(data, d => d.domain);
    // Save more data in the array clusters
    const clusters = Array.from(domains, ([domain, docs]) => ({
        domain,
        docs,
        totalScore: d3.sum(docs, d => d.score),
    }));

    console.log("Domains found:", Array.from(domains.keys()));
    console.log("Clusters:", clusters);
    console.log("Domains total Scores:", clusters.map(d => d.totalScore));


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

    // Define function to calculate radius by either score or total score for doc or domain/cluster
    const docRadiusScale = d3.scaleLinear()
        .domain(d3.extent(data, d => d.score))
        .range([18, 50]);
    const clusterRadiusScale = d3.scaleSqrt()
        .domain([0, d3.max(clusters, d => d.totalScore)])
        .range([30, 250]);

    
    const centerX = virtualWidth / 2;
    const centerY = virtualHeight / 2;
    
    // First simulation to position the cluster-centers (each cluster being a domain)
    const clusterSim = d3.forceSimulation(clusters)
        .force("charge", d3.forceManyBody().strength(1000))
        .force("center", d3.forceCenter(centerX, centerY))
        .force("collide", d3.forceCollide().radius(d => clusterRadiusScale(d.totalScore)+18))
        .stop();

    for (let i = 0; i < 200; i++) clusterSim.tick();

    // Fix cluster positions and set radius
    clusters.forEach(cluster => {
        cluster.fx = cluster.x;
        cluster.fy = cluster.y;
        cluster.radius = clusterRadiusScale(cluster.totalScore);
    });

    console.log("Cluster positions:", clusters.map(c => ({domain: c.domain, x: c.x, y: c.y})));


    // Calculate initial positioning of the zoom (view) based on content bounds
    let contentBounds, initialTransform;
    try {
        contentBounds = {
            minX: Math.min(...clusters.map(c => c.x)) - 50,
            maxX: Math.max(...clusters.map(c => c.x)) + 50,
            minY: Math.min(...clusters.map(c => c.y)) - 50,
            maxY: Math.max(...clusters.map(c => c.y)) + 50
        };
        
        console.log("Content bounds calculated:", contentBounds);
        
        const contentWidth = contentBounds.maxX - contentBounds.minX;
        const contentHeight = contentBounds.maxY - contentBounds.minY;
        
        // Calculate scale to fit content in canvas with some padding
        const padding = 0.35;
        const scaleX = (canvasWidth * (1-padding)) / contentWidth;
        const scaleY = (canvasHeight * (1-padding)) / contentHeight;
        const optimalScale = Math.min(scaleX, scaleY, 1.2);
        
        // Center of the content
        const contentCenterX = (contentBounds.minX + contentBounds.maxX) / 2;
        const contentCenterY = (contentBounds.minY + contentBounds.maxY) / 2;
        
        // Calculate translates that are the coordinates, so that our view/zoom is centered
        const translateX = canvasWidth / 2 - contentCenterX * optimalScale *1.2; // Got the 1.2 factor from testing. Seems to center the view nicely
        const translateY = canvasHeight / 2 - contentCenterY * optimalScale *1.2;

        console.log(`Content Center: (${contentCenterX}, ${contentCenterY})`);
        console.log(`Viewport Center: (${canvasWidth / 2}, ${canvasHeight / 2})`);
        console.log(`Calculated Translate: (${translateX}, ${translateY})`);

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
    
    // Call to position the zoom/view at correct translate and scale
    svg.call(zoom.transform, initialTransform);

    // Map domain names to cluster centers
    const clusterCenterMap = Object.fromEntries(clusters.map(c => [c.domain, c]));

    // Position documents around their cluster centers with improved force simulation
    const docSim = d3.forceSimulation(data)
        .force("x", d3.forceX(d => clusterCenterMap[d.domain]?.x || centerX).strength(0.8))
        .force("y", d3.forceY(d => clusterCenterMap[d.domain]?.y || centerY).strength(0.8))
        .force("collision", d3.forceCollide().radius(d => Math.max(18, docRadiusScale(d.score)) + 4))
        .force("charge", d3.forceManyBody().strength(20))
        .alphaDecay(0.01)
        .velocityDecay(0.2)
        .on("tick", ticked);


    const clusterGroups = mainGroup.selectAll(".cluster")
        .data(clusters)
        .enter().append("g")
        .attr("class", "cluster")
        .attr("transform", d => `translate(${d.x},${d.y})`);

    // Add background circles for domains (sized depending on total score)
    clusterGroups.append("circle")
        .attr("r", d => Math.max(30, clusterRadiusScale(d.totalScore)))
        .attr("fill", d => color(d.domain))
        .attr("fill-opacity", 0.08)
        .attr("stroke", d => color(d.domain))
        .attr("stroke-width", 3)
        .attr("stroke-opacity", 0.4)
        .attr("stroke-dasharray", "5,5");

    clusterGroups.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".3em")
        .style("font-weight", "bold")
        .style("font-size", "20px")
        .style("pointer-events", "none")
        .text(d => d.domain.toUpperCase())
        .attr("fill", d => color(d.domain))
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .attr("paint-order", "stroke");

    // Determine top 10 documents by score
    const topDocs = data
        .slice()
        .sort((a, b) => b.score - a.score)
        .slice(0, 10);

    const topDocSet = new Set(topDocs);

    console.log("Top 10 Documents Set:", topDocSet);

    const nodeGroups = mainGroup.selectAll(".doc-node-group")
        .data(data)
        .enter().append("g")
        .attr("class", "doc-node-group");

    // Add foreground circles for documents (sized depending on their score)
    const node = nodeGroups.append("circle")
        .attr("class", "doc-node")
        .attr("r", d => Math.max(18, docRadiusScale(d.score)))
        .attr("fill", d => color(d.domain))
        .attr("fill-opacity", d => topDocSet.has(d) ? 0.9 : 0.7) // Make top 10 docs more opaque
        .attr("stroke", "#333")
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.9);

    // Add titles inside bubbles for the larger ones
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
        .style("display", d => docRadiusScale(d.score) > 35 ? "block" : "none");

    // Add event listeners to the group to prevent flickering
    nodeGroups
        .on("mouseover", (event, d) => {
            d3.select(event.currentTarget).select("circle")
                .transition().duration(150)
                .attr("fill-opacity", 1)
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
                .attr("fill-opacity", d => topDocSet.has(d) ? 0.9 : 0.7)
                .attr("stroke-width", 1.5);
            
            tooltip.style("visibility", "hidden");
        })
        .on("click", (event, d) => window.open(d.url, "_blank"))
        .style("cursor", "pointer");

    // Remove any existing tooltips before creating a new one (tooltip is a preview of the document)
    d3.selectAll(".tooltip").remove();
    const tooltip = d3.select("body").append("div")
        .attr("class", "tooltip");

    // Add zoom controls (top left corner of svg)
    const controls = svg.append("g")
        .attr("class", "zoom-controls")
        .attr("transform", `translate(20, 20)`);

    const controlsBackground = controls.append("rect")
        .attr("width", 60)
        .attr("height", 115)
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
        .attr("transform", "translate(10, 80)")
        .style("cursor", "pointer");

    resetBtn.append("rect")
        .attr("width", 40)
        .attr("height", 25)
        .attr("fill", "#28a745")
        .attr("rx", 3);

    resetBtn.append("text")
        .attr("x", 20)
        .attr("y", 14)
        .attr("text-anchor", "middle")
        .attr("fill", "white")
        .attr("font-size", "9px")
        .text("Default");

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

    function ticked() {
        nodeGroups.attr("transform", d => `translate(${d.x},${d.y})`);
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
    const mainContent = document.getElementById("main-content");
    const llmResponseBox = document.getElementById("llm-response-text");

    // Remove centered class after first submission
    header.classList.remove("centered");
    mainContent.style.display = "flex";

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
                <span class="result-domain">${result.domain}</span>
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

function formatLLMResponse(text) {
    if (!text) return "No AI answer available.";

    return text
        .replace(/### (.*$)/gim, '<h3>$1</h3>')                 // ### -> <h3>
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')     // **bold**
        .replace(/^- (.*$)/gim, '<li>$1</li>')                  // - bullet points
        .replace(/\n{2,}/g, '</p><p>')                          // Double newline → paragraph
        .replace(/\n/g, '<br>')                                 // Single newline
        .replace(/^/, '<p>')                                    // Wrap start in <p>
        .concat('</p>');                                        // Wrap end in </p>
}
