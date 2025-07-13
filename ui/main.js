function loadDataAndRender(query) {
    d3.json("data.json").then(data => {
        const svg = d3.select("#bubbleChart");
        const width = +svg.attr("width");
        const height = +svg.attr("height");

        svg.selectAll("*").remove();

        // Parse topics into arrays and identify primary/secondary
        data.forEach(d => {
            d.topics = d.topic.split(",").map(t => t.trim());
            d.primaryTopic = d.topics[0];
            d.secondaryTopics = d.topics.slice(1);
        });

        // Group by primary topic
        const topics = d3.group(data, d => d.primaryTopic);
        const clusters = Array.from(topics, ([topic, docs]) => ({
            topic,
            docs,
            count: docs.length,
            totalScore: d3.sum(docs, d => d.score),
            avgScore: d3.mean(docs, d => d.score)
        }));

        const color = d3.scaleOrdinal(d3.schemeCategory10);

        const docRadiusScale = d3.scaleSqrt()
            .domain([0, d3.max(data, d => d.score)])
            .range([5, 50]);

        const clusterRadiusScale = d3.scaleSqrt()
            .domain([0, d3.max(clusters, d => d.totalScore)])
            .range([30, 80]);

        // Position clusters
        const clusterSimulation = d3.forceSimulation(clusters)
            .force("charge", d3.forceManyBody().strength(5))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => clusterRadiusScale(d.totalScore) + 10))
            .on("tick", ticked);

        setTimeout(() => {
            clusterSimulation.stop();

            // Fix cluster centers
            clusters.forEach(d => {
                d.fx = d.x;
                d.fy = d.y;
                d.radius = clusterRadiusScale(d.totalScore);
            });

            // Map topic names to cluster centers
            const clusterCenterMap = Object.fromEntries(clusters.map(c => [c.topic, c]));

            const docSim = d3.forceSimulation(data)
                .force("x", d3.forceX(d => clusterCenterMap[d.primaryTopic]?.x).strength(0.5))
                .force("y", d3.forceY(d => clusterCenterMap[d.primaryTopic]?.y).strength(0.5))
                .force("collision", d3.forceCollide().radius(d => docRadiusScale(d.score) + 3))
                .force("charge", d3.forceManyBody().strength(2))
                .force("secondaryAttract", () => {
                data.forEach(d => {
                    d.secondaryTopics.forEach(topic => {
                    const cluster = clusterCenterMap[topic];
                    if (cluster) {
                        d.vx += (cluster.x - d.x) * 0.008; // weak attraction
                        d.vy += (cluster.y - d.y) * 0.008;
                    }
                    });
                });
                })
                .on("tick", ticked);
        }, 150);

        const clusterGroups = svg.selectAll(".cluster")
            .data(clusters)
            .enter().append("g")
            .attr("class", "cluster");

        clusterGroups.append("text")
            .attr("text-anchor", "middle")
            .attr("dy", ".3em")
            .style("font-weight", "bold")
            .style("font-size", d => Math.min(16, clusterRadiusScale(d.totalScore) / 2) + "px")
            .text(d => d.topic.toUpperCase())
            .attr("fill", d => color(d.topic));

        const node = svg.selectAll("circle")
            .data(data)
            .enter().append("circle")
            .attr("class", "doc-node")
            .attr("r", d => docRadiusScale(d.score))
            .attr("fill", d => color(d.primaryTopic))
            .attr("fill-opacity", 0.5)
            .attr("stroke", "#333")
            .attr("stroke-width", 1)
            .attr("stroke-opacity", 0.5)
            .on("mouseover", (event, d) => {
                tooltip.style("visibility", "visible")
                .html(`<strong>${d.title}</strong><br>${d.snippet}<br><a href="${d.url}" target="_blank">Visit</a>`);
            })
            .on("mousemove", event => {
                tooltip.style("top", (event.pageY - 10) + "px")
                .style("left", (event.pageX + 10) + "px");
            })
            .on("mouseout", () => tooltip.style("visibility", "hidden"))
            .on("click", (event, d) => window.open(d.url, "_blank"));

        const topDocs = Array.from(d3.group(data, d => d.primaryTopic), ([topic, docs]) =>
            docs.sort((a, b) => d3.descending(a.score, b.score)).slice(0, 2)
            ).flat();

        const labels = svg.selectAll(".doc-label")
            .data(topDocs)
            .enter()
            .append("text")
            .attr("class", "doc-label")
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("fill", "#333")
            .text(d => d.title);

        const tooltip = d3.select("body").append("div")
            .attr("class", "tooltip");

        function ticked() {
            node.attr("cx", d => d.x).attr("cy", d => d.y);
            clusterGroups.attr("transform", d => `translate(${d.x},${d.y})`);
            labels
                .attr("x", d => d.x)
                .attr("y", d => d.y - docRadiusScale(d.score) - 6);
        }
    });
}


document.getElementById("queryInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        const query = e.target.value.trim();
        if (!query) return;

        console.log("Search query submitted:", query);

        const header = document.getElementById("header");
        const results = document.getElementById("results");

        // Remove centered class after first submission
        header.classList.remove("centered");
        results.style.display = "block";

        // Clear previous results (optional)
        d3.select("#bubbleChart").selectAll("*").remove();

        // Load & visualize
        loadDataAndRender(query);

        //Part b)
        //d3.json("data.json").then(data => {
        //    exportResultsToText(data);
        //});
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
