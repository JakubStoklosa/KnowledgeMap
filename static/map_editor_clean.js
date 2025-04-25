// Initial setup
const mapDataElement = document.getElementById("map-data");

const mapId = mapDataElement.getAttribute("data-map-id");
let nodes = JSON.parse(mapDataElement.getAttribute("data-nodes"));
let links = JSON.parse(mapDataElement.getAttribute("data-links"));
const labelToNode = {};
nodes.forEach(n => labelToNode[n.label] = n);
links = links.map(l => ({ 
    source: labelToNode[l.sourceLabel], 
    target: labelToNode[l.targetLabel], 
    type: l.type || 'line',
    distance: l.distance || 100
}));

let isLinkMode = false;
let selectedSourceNode = null;
let isDeleteMode = false;
let actionHistory = [];
let selectedResizableNode = null;
let selectedResizableLink = null;

// Ensure resize popup is properly styled
const resizePopup = document.getElementById("resize-popup");


// Create link resize popup
const linkResizePopup = document.createElement("div");
linkResizePopup.id = "link-resize-popup";


// Create buttons for link resizing
const increaseLinkButton = document.createElement("button");
increaseLinkButton.textContent = "+";


const decreaseLinkButton = document.createElement("button");
decreaseLinkButton.textContent = "-";


// Add buttons to the link resize popup
linkResizePopup.appendChild(increaseLinkButton);
linkResizePopup.appendChild(decreaseLinkButton);
document.body.appendChild(linkResizePopup);

// Add resize button event listeners
document.getElementById("increase-size").addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Increase size clicked");
    if (selectedResizableNode) {
        console.log("Resizing node larger:", selectedResizableNode);
        const shape = selectedResizableNode.shape;
        if (shape === "circle") {
            const circle = d3.select(selectedResizableNode.element).select("circle");
            const newRadius = +circle.attr("r") + 5;
            circle.attr("r", newRadius);
        
            // ✅ Save size to data
            selectedResizableNode.data.size = newRadius;
        } else {
            const rect = d3.select(selectedResizableNode.element).select("rect");
            const newWidth = +rect.attr("width") + 5;
            const newHeight = +rect.attr("height") + 5;
            rect.attr("width", newWidth).attr("height", newHeight);
        
            // ✅ Save size to data
            selectedResizableNode.data.size = { width: newWidth, height: newHeight };
        }
        
    }
});

document.getElementById("decrease-size").addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Decrease size clicked");
    if (selectedResizableNode) {
        console.log("Resizing node smaller:", selectedResizableNode);
        const shape = selectedResizableNode.shape;
        if (shape === "circle") {
            const circle = d3.select(selectedResizableNode.element).select("circle");
            const newR = Math.max(10, +circle.attr("r") - 5);
            console.log("New circle radius:", newR);
            circle.attr("r", newR);
        } else {
            const rect = d3.select(selectedResizableNode.element).select("rect");
            const newW = Math.max(10, +rect.attr("width") - 5);
            const newH = Math.max(10, +rect.attr("height") - 5);
            console.log("New rectangle size:", newW, newH);
            rect.attr("width", newW).attr("height", newH);
        }
    }
});

// Add link resize button event listeners
increaseLinkButton.addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Increase link length clicked");
    if (selectedResizableLink) {
        const link = selectedResizableLink.link;
        link.distance = Math.min(300, link.distance + 20);
        console.log("New link distance:", link.distance);
        updateSimulationLinks();
    }
});

decreaseLinkButton.addEventListener("click", function(event) {
    event.stopPropagation();
    console.log("Decrease link length clicked");
    if (selectedResizableLink) {
        const link = selectedResizableLink.link;
        link.distance = Math.max(20, link.distance - 20);
        console.log("New link distance:", link.distance);
        updateSimulationLinks();
    }
});

// Function to update link distances in the simulation
function updateSimulationLinks() {
    simulation.force("link", d3.forceLink(links).distance(d => d.distance));
    simulation.alpha(0.3).restart();
}

// Hide popups when clicking elsewhere
document.addEventListener("click", function(event) {
    if (!resizePopup.contains(event.target)) {
        resizePopup.style.display = "none";
        selectedResizableNode = null;
    }
    if (!linkResizePopup.contains(event.target)) {
        linkResizePopup.style.display = "none";
        selectedResizableLink = null;
    }
});


// Dropdown toggle
document.getElementById("view-editors-btn").addEventListener("click", function() {
    const dropdown = document.getElementById("editors-dropdown");
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
});

// Copy map ID
function copyMapId() {
    const mapIdElement = document.getElementById("display-map-id");
    const range = document.createRange();
    range.selectNode(mapIdElement);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    window.getSelection().removeAllRanges();
    alert('Map ID copied to clipboard!');
}

// SVG and simulation
const svg = d3.select("#map-container")
    .append("svg")
    .attr("width", "100%")
    .attr("height", "100%");
const svgGroup = svg.append("g");

const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on("zoom", event => svgGroup.attr("transform", event.transform));
svg.call(zoom);

// Define arrowhead marker
svg.append("defs").append("marker")
    .attr("id", "arrowhead")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 30)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "black");

const simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-30))
    .force("center", d3.forceCenter(window.innerWidth / 2, window.innerHeight / 2))
    .on("tick", ticked);

function updateVisualization() {
    // Update nodes
    const nodeElements = svgGroup.selectAll(".node").data(nodes, d => d.id);
    
    // Enter new nodes
    const nodeEnter = nodeElements.enter()
        .append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended));
    
    // Add node click behavior explicitly
    nodeEnter.on("click", function(event, node) {
        nodeClicked(event, node, this);
    });
    
    // Add shapes based on node type
    nodeEnter.each(function(d) {
        if (d.shape === "square") {
            const width = d.size?.width || 60;
            const height = d.size?.height || 60;
            d3.select(this).append("rect")
                .attr("x", -width / 2)
                .attr("y", -height / 2)
                .attr("width", width)
                .attr("height", height)
                .attr("fill", d.color);
        } else {
            const radius = d.size || 35;
            d3.select(this).append("circle")
                .attr("r", radius)
                .attr("fill", d.color);
        }
    });

    // Add node labels and descriptions
    nodeEnter.append("text")
        .attr("class", "node-label")
        .attr("dy", 4)
        .text(d => d.label);
    
    nodeEnter.append("title")
        .text(d => d.description);
    
    // Remove old nodes
    nodeElements.exit().remove();

    // Update links
    const linkElements = svgGroup.selectAll(".link").data(links);
    
    // Enter new links
    const linkEnter = linkElements.enter()
        .append("line")
        .attr("class", "link")
        .attr("stroke", "black")
        .attr("stroke-width", 2)
        .attr("marker-end", d => d.type === 'arrow' ? 'url(#arrowhead)' : null)
        .merge(linkElements)
        .attr("marker-end", d => d.type === 'arrow' ? 'url(#arrowhead)' : null);
    
    // Add click event for links
    linkEnter.on("click", function(event, link) {
        linkClicked(event, link, this);
    });
    
    // Remove old links
    linkElements.exit().remove();

    // Update simulation
    simulation.nodes(nodes);
    updateSimulationLinks();
}

function ticked() {
    svgGroup.selectAll(".node")
        .attr("transform", d => `translate(${d.x},${d.y})`);
    
    svgGroup.selectAll(".link")
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);
}

function nodeClicked(event, node, element) {
    console.log("Node clicked:", node);
    console.log("isLinkMode:", isLinkMode, "isDeleteMode:", isDeleteMode);
    
    // Hide link resize popup first
    selectedResizableLink = null;
    
    // Handle node deletion
    if (isDeleteMode) {
        console.log("Deleting node:", node);
        nodes = nodes.filter(n => n !== node);
        const removedLinks = links.filter(l => l.source === node || l.target === node);
        links = links.filter(l => l.source !== node && l.target !== node);
        actionHistory.push({ type: 'delete-node', node, links: removedLinks });
        updateVisualization();
        return;
    }

    // Handle link creation
    if (isLinkMode) {
        if (selectedSourceNode) {
            console.log("Creating link from", selectedSourceNode, "to", node);
            const type = document.getElementById('link-type').value;
            const newLink = { 
                source: selectedSourceNode, 
                target: node, 
                type, 
                distance: 100 
            };
            links.push(newLink);
            actionHistory.push({ type: 'add-link', link: newLink });
            selectedSourceNode = null;
            updateVisualization();
        } else {
            console.log("Selected source node:", node);
            selectedSourceNode = node;
        }
        return;
    }

    // Handle node resize (when not in link or delete mode)
    console.log("Showing resize popup for node:", node);
    selectedResizableNode = {
        element: element,
        shape: node.shape,
        data: node

    };
    
    // Position the resize popup near the node
    const rect = element.getBoundingClientRect();
    const bodyRect = document.body.getBoundingClientRect();
    
    const left = rect.left - bodyRect.left + window.scrollX + rect.width/2;
    const top = rect.top - bodyRect.top + window.scrollY + rect.height/2;
    
    console.log("Positioning popup at:", left, top);
    resizePopup.style.left = `${left}px`;
    resizePopup.style.top = `${top}px`;
    const descriptionDiv = document.getElementById("popup-description");
    descriptionDiv.textContent = node.description || "No description available";
    resizePopup.style.display = "block";
    // Stop event propagation
    event.stopPropagation();
}

function linkClicked(event, link, element) {
    console.log("Link clicked:", link);
    
    // Hide node resize popup first
    selectedResizableNode = null;
    
    // Don't show resize popup if in delete or link mode
    if (isDeleteMode) {
        console.log("Deleting link:", link);
        links = links.filter(l => l !== link);
        actionHistory.push({ type: 'delete-link', link });
        updateVisualization();
        return;
    }
    
    if (isLinkMode) {
        return;
    }
    
    // Handle link resizing
    console.log("Showing resize popup for link");
    selectedResizableLink = {
        element: element,
        link: link
    };
    
    // Position the link resize popup at the middle of the link
    const x1 = link.source.x;
    const y1 = link.source.y;
    const x2 = link.target.x;
    const y2 = link.target.y;
    
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2;
    
    // Calculate screen position from SVG coordinates
    const svgRect = svg.node().getBoundingClientRect();
    const transform = d3.zoomTransform(svg.node());
    
    const screenX = svgRect.left + transform.applyX(midX);
    const screenY = svgRect.top + transform.applyY(midY);
    
    console.log("Positioning link popup at:", screenX, screenY);
    linkResizePopup.style.left = `${screenX}px`;
    linkResizePopup.style.top = `${screenY}px`;
    linkResizePopup.style.display = "block";

    // Stop event propagation
    event.stopPropagation();
}

function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

document.getElementById('delete-mode-btn').addEventListener('click', function() {
    isDeleteMode = !isDeleteMode;
    document.getElementById('delete-mode-btn').textContent = isDeleteMode ? 'Delete: ON' : 'Delete';
});

document.getElementById('link-mode').addEventListener('click', function() {
    isLinkMode = !isLinkMode;
    document.getElementById('link-mode').textContent = isLinkMode ? 'Link Mode On' : 'Link Mode Off';
});

document.getElementById('undo-action').addEventListener('click', function() {
    const lastAction = actionHistory.pop();
    if (!lastAction) return;

    if (lastAction.type === 'add-node') {
        nodes = nodes.filter(n => n !== lastAction.node);
        links = links.filter(l => l.source !== lastAction.node && l.target !== lastAction.node);
    } else if (lastAction.type === 'delete-node') {
        nodes.push(lastAction.node);
        links.push(...lastAction.links);
    } else if (lastAction.type === 'delete-link') {
        links.push(lastAction.link);
    } else if (lastAction.type === 'add-link') {
        links = links.filter(l => l !== lastAction.link);
    }

    updateVisualization();
});

document.getElementById('zoom-in').addEventListener('click', function() {
    svg.transition().call(zoom.scaleBy, 1.2);
});

document.getElementById('zoom-out').addEventListener('click', function() {
    svg.transition().call(zoom.scaleBy, 0.8);
});

document.getElementById('save-map').addEventListener('click', function() {
    fetch('/save_map', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mapId,
            nodes: nodes.map(n => {
                const element = d3.selectAll(".node").filter(d => d === n).node();
                let size = 35; // default for circles
                if (n.shape === "circle") {
                    const circle = d3.select(element).select("circle");
                    size = +circle.attr("r");
                } else {
                    const rect = d3.select(element).select("rect");
                    size = { width: +rect.attr("width"), height: +rect.attr("height") };
                }

                return {
                    label: n.label,
                    description: n.description,
                    x: n.x,
                    y: n.y,
                    shape: n.shape,
                    color: n.color,
                    size
                };
            }),

            
            links: links.map(l => ({
                sourceLabel: l.source.label,
                targetLabel: l.target.label,
                type: l.type || 'line',
                distance: l.distance || 100  // Save the custom distance
            }))
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            alert('Map saved successfully!');
        } else {
            alert('Error saving map: ' + data.message);
        }
    })
    .catch(err => {
        console.error(err);
        alert('Failed to save map');
    });
});

function createNode() {
    const label = document.getElementById('node-label').value.trim();
    const description = document.getElementById('node-description').value.trim();
    const shape = document.getElementById('node-shape').value;
    const color = document.getElementById('node-color').value;

    if (!label) {
        alert("Please enter a node label");
        return;
    }

    const newNode = {
        id: nodes.length,
        label,
        description,
        shape,
        color,
        x: window.innerWidth / 2,
        y: window.innerHeight / 2
    };

    nodes.push(newNode);
    actionHistory.push({ type: 'add-node', node: newNode });
    updateVisualization();

    document.getElementById('node-label').value = '';
    document.getElementById('node-description').value = '';
}

document.getElementById('back-to-maps-btn').addEventListener('click', function() {
    const confirmed = confirm("Have you saved your changes? Unsaved work will be lost. Proceed?");
    if (confirmed) {
        window.location.href = "/view_personal_maps";
    }
});

function renderAverageRating() {
    const container = document.getElementById("average-rating-stars");
    const rating = parseFloat(container.dataset.rating || 0);
    container.innerHTML = "";

    for (let i = 1; i <= 5; i++) {
        container.innerHTML += i <= rating ? "★" : "☆";
    }
}
renderAverageRating();

const rateButton = document.getElementById("rate-map-btn");
const ratingPopup = document.getElementById("rating-popup");

rateButton.addEventListener("click", () => {
    if (ratingPopup.style.display === "block") {
        ratingPopup.style.display = "none";
        return;
    }
    const rect = rateButton.getBoundingClientRect();
    ratingPopup.style.left = `${rect.left}px`;
    ratingPopup.style.top = `${rect.bottom + 5}px`;
    ratingPopup.style.display = "block";
});

document.querySelectorAll("#rating-popup .star").forEach(star => {
    star.addEventListener("click", function () {
        const rating = this.dataset.value;
        fetch("/rate_map", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mapId, rating })
        }).then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                alert("Thanks for rating!");
                ratingPopup.style.display = "none";
                location.reload();  // reload to show new average
            }
        });
    });
});

// Render number of raters and toggle rater list
const ratingCountSpan = document.getElementById('rating-count');
const raterList = document.getElementById('rater-list');
const raterListItems = document.getElementById('rater-list-items');

ratingCountSpan.addEventListener('click', () => {
    const visible = raterList.style.display === 'block';
    raterList.style.display = visible ? 'none' : 'block';
});

// Populate rater list
const ratersData = JSON.parse(document.getElementById('average-rating-stars').getAttribute('data-raters'));
ratersData.forEach(rater => {
    const li = document.createElement('li');
    li.textContent = `${rater.username}: ${rater.rating} star${rater.rating !== 1 ? 's' : ''}`;
    raterListItems.appendChild(li);
});



updateVisualization();
console.log("Visualization initialized with", nodes.length, "nodes and", links.length, "links");
    updateVisualization();

    