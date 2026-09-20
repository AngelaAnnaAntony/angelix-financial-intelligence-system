/**
 * ============================================================
 * ANGELIX - REPORT HISTORY
 * ============================================================
 *
 * Production-oriented report history frontend.
 *
 * Features:
 * - Loads reports from the current Angelix page data
 * - Uses real database-backed report records
 * - Search
 * - Report type filtering
 * - Status filtering
 * - Format filtering
 * - Date-range filtering
 * - Pagination
 * - Select all
 * - Bulk selection
 * - Real report viewing
 * - Real report downloading
 * - Real report deletion
 * - Confirmation modal
 * - Empty state
 * - Toast notifications
 * - Light/Dark mode compatibility
 *
 * The page is rendered by Flask and receives the current
 * organization's reports from report_routes.py.
 *
 * ============================================================
 */

document.addEventListener(
    "DOMContentLoaded",
    () => {
        "use strict";

        /* =====================================================
           CONFIGURATION
        ===================================================== */

        const PAGE_SIZE = 5;

        const organizationId =
            getOrganizationId();

        const currentPath =
            window.location.pathname;


        /* =====================================================
           DOM REFERENCES
        ===================================================== */

        const tableBody =
            document.getElementById(
                "reportHistoryTableBody"
            );

        const searchInput =
            document.getElementById(
                "reportHistorySearch"
            );

        const clearSearchBtn =
            document.getElementById(
                "clearReportSearchBtn"
            );

        const reportTypeFilter =
            document.getElementById(
                "historyReportType"
            );

        const statusFilter =
            document.getElementById(
                "historyReportStatus"
            );

        const formatFilter =
            document.getElementById(
                "historyReportFormat"
            );

        const dateFilter =
            document.getElementById(
                "historyDateRange"
            );

        const clearFiltersBtn =
            document.getElementById(
                "clearReportFiltersBtn"
            );

        const resetFiltersBtn =
            document.getElementById(
                "resetHistoryFiltersBtn"
            );

        const refreshBtn =
            document.getElementById(
                "refreshReportHistoryBtn"
            );

        const emptyState =
            document.getElementById(
                "reportHistoryEmptyState"
            );

        const selectAllCheckbox =
            document.getElementById(
                "selectAllReports"
            );

        const bulkToolbar =
            document.getElementById(
                "historyBulkToolbar"
            );

        const selectedCountElement =
            document.getElementById(
                "selectedReportsCount"
            );

        const bulkDownloadBtn =
            document.getElementById(
                "bulkDownloadBtn"
            );

        const bulkDeleteBtn =
            document.getElementById(
                "bulkDeleteBtn"
            );

        const deleteModal =
            document.getElementById(
                "historyDeleteModal"
            );

        const closeDeleteModalBtn =
            document.getElementById(
                "closeHistoryDeleteModal"
            );

        const cancelDeleteBtn =
            document.getElementById(
                "cancelHistoryDeleteBtn"
            );

        const confirmDeleteBtn =
            document.getElementById(
                "confirmHistoryDeleteBtn"
            );

        const deleteMessage =
            document.getElementById(
                "deleteReportsMessage"
            );

        const toastContainer =
            document.getElementById(
                "reportHistoryToastContainer"
            );

        const previousPageBtn =
            document.getElementById(
                "historyPreviousPage"
            );

        const nextPageBtn =
            document.getElementById(
                "historyNextPage"
            );

        const showingFrom =
            document.getElementById(
                "historyShowingFrom"
            );

        const showingTo =
            document.getElementById(
                "historyShowingTo"
            );

        const showingTotal =
            document.getElementById(
                "historyShowingTotal"
            );


        /* =====================================================
           STATE
        ===================================================== */

        let reports = [];

        let filteredReports = [];

        let currentPage = 1;

        let reportsToDelete = [];

        let loading = false;

        /* =====================================================
           CSRF PROTECTION
        ===================================================== */

        function getCSRFToken() {
            /*
             * Prefer a meta tag if the base template exposes one.
             */
            const metaToken =
                document.querySelector(
                    'meta[name="csrf-token"]'
                );

            if (
                metaToken &&
                metaToken.content
            ) {
                return metaToken.content;
            }

            /*
             * Flask-WTF normally renders a hidden
             * csrf_token input inside forms.
             */
            const inputToken =
                document.querySelector(
                    'input[name="csrf_token"]'
                );

            if (
                inputToken &&
                inputToken.value
            ) {
                return inputToken.value;
            }

            return "";
        }

        /* =====================================================
           ORGANIZATION ID
        ===================================================== */

        function getOrganizationId() {
            const match =
                window.location.pathname.match(
                    /\/organizations\/(\d+)\/reports/
                );

            if (match) {
                return match[1];
            }

            return null;
        }


        /* =====================================================
           SAFE TEXT HELPERS
        ===================================================== */

        function escapeHTML(
            value
        ) {
            return String(
                value ?? ""
            )
                .replace(
                    /&/g,
                    "&amp;"
                )
                .replace(
                    /</g,
                    "&lt;"
                )
                .replace(
                    />/g,
                    "&gt;"
                )
                .replace(
                    /"/g,
                    "&quot;"
                )
                .replace(
                    /'/g,
                    "&#039;"
                );
        }


        function formatDate(
            value
        ) {
            if (!value) {
                return "—";
            }

            const date =
                new Date(value);

            if (
                Number.isNaN(
                    date.getTime()
                )
            ) {
                return String(
                    value
                );
            }

            return new Intl.DateTimeFormat(
                "en-IN",
                {
                    day: "2-digit",
                    month: "short",
                    year: "numeric",
                }
            ).format(
                date
            );
        }


        function formatPeriod(
            report
        ) {
            const start =
                report.period_start ||
                report.periodStart;

            const end =
                report.period_end ||
                report.periodEnd;

            if (!start && !end) {
                return "—";
            }

            if (
                start &&
                end
            ) {
                return (
                    `${formatDate(start)} – ` +
                    `${formatDate(end)}`
                );
            }

            return formatDate(
                start || end
            );
        }


        function formatFileSize(
            bytes
        ) {
            const value =
                Number(bytes || 0);

            if (!value) {
                return "—";
            }

            if (
                value <
                1024
            ) {
                return (
                    `${value} B`
                );
            }

            if (
                value <
                1024 * 1024
            ) {
                return (
                    `${(
                        value / 1024
                    ).toFixed(2)} KB`
                );
            }

            return (
                `${(
                    value /
                    (1024 * 1024)
                ).toFixed(2)} MB`
            );
        }


        function getFileFormat(
            report
        ) {
            const value =
                report.file_format ||
                report.format ||
                "pdf";

            return String(
                value
            )
                .replace(
                    ".",
                    ""
                )
                .toUpperCase();
        }


        function getReportName(
            report
        ) {
            return (
                report.title ||
                report.name ||
                "Financial Report"
            );
        }


        function getReportType(
            report
        ) {
            return (
                report.report_type ||
                report.type ||
                "financial_statement"
            );
        }


        function getReportTypeLabel(
            report
        ) {
            const type =
                getReportType(
                    report
                );

            const labels = {
                financial_statement:
                    "Financial Statement",
                financial_analysis:
                    "Financial Analysis",
                financial_summary:
                    "Financial Summary",
                profit_loss:
                    "Profit & Loss",
                balance_sheet:
                    "Balance Sheet",
                cash_flow:
                    "Cash Flow",
                ai_analysis:
                    "AI Financial Analysis",
            };

            if (
                labels[type]
            ) {
                return labels[type];
            }

            return String(
                type
            )
                .replaceAll(
                    "_",
                    " "
                )
                .replace(
                    /\b\w/g,
                    character =>
                        character.toUpperCase()
                );
        }


        function normalizeStatus(
            report
        ) {
            const status =
                String(
                    report.status ||
                    "pending"
                )
                    .trim()
                    .toLowerCase();

            if (
                status ===
                "ready"
            ) {
                return "completed";
            }

            return status;
        }


        function getStatusLabel(
            status
        ) {
            const labels = {
                completed:
                    "Completed",
                ready:
                    "Completed",
                processing:
                    "Processing",
                pending:
                    "Pending",
                failed:
                    "Failed",
                error:
                    "Failed",
            };

            return (
                labels[status] ||
                String(
                    status
                )
                    .replaceAll(
                        "_",
                        " "
                    )
                    .replace(
                        /\b\w/g,
                        character =>
                            character.toUpperCase()
                    )
            );
        }


        function getStatusClass(
            status
        ) {
            const normalized =
                normalizeStatus({
                    status
                });

            if (
                normalized ===
                "completed"
            ) {
                return "completed";
            }

            if (
                normalized ===
                "processing"
            ) {
                return "processing";
            }

            if (
                normalized ===
                "pending"
            ) {
                return "processing";
            }

            if (
                normalized ===
                "failed" ||
                normalized ===
                "error"
            ) {
                return "failed";
            }

            return "processing";
        }


        function getFormatIcon(
            format
        ) {
            const normalized =
                String(
                    format || ""
                ).toLowerCase();

            if (
                normalized ===
                "pdf"
            ) {
                return "📕";
            }

            if (
                normalized ===
                "xlsx" ||
                normalized ===
                "xls"
            ) {
                return "📗";
            }

            if (
                normalized ===
                "csv"
            ) {
                return "📊";
            }

            return "📄";
        }


        /* =====================================================
           API / DATA LOADING
        ===================================================== */

        async function loadReports() {
            if (loading) {
                return;
            }

            loading = true;

            setLoadingState(
                true
            );

            try {
                /*
                 * The report history page is server-rendered.
                 *
                 * The Flask route provides the report collection
                 * through the page. We first look for a JSON data
                 * object exposed by the template.
                 */

                const embedded =
                    getEmbeddedReports();

                if (
                    Array.isArray(
                        embedded
                    )
                ) {
                    reports =
                        normalizeReports(
                            embedded
                        );

                    updateStatistics();

                    renderReports();

                    return;
                }

                /*
                 * Fallback:
                 * Request the current report-history page and
                 * extract the server-provided report JSON if the
                 * template exposes it.
                 */

                const response =
                    await fetch(
                        currentPath,
                        {
                            method: "GET",
                            headers: {
                                Accept:
                                    "text/html",
                            },
                            credentials:
                                "same-origin",
                            cache: "no-store",
                        }
                    );

                if (
                    !response.ok
                ) {
                    throw new Error(
                        `Unable to load reports (${response.status}).`
                    );
                }

                const html =
                    await response.text();

                const parsed =
                    extractReportsFromHTML(
                        html
                    );

                if (
                    Array.isArray(
                        parsed
                    )
                ) {
                    reports =
                        normalizeReports(
                            parsed
                        );

                    updateStatistics();

                    renderReports();

                    return;
                }

                /*
                 * If the current template does not expose JSON,
                 * retain an empty real-data state rather than
                 * displaying fake reports.
                 */

                reports = [];

                updateStatistics();

                renderReports();

            } catch (error) {

                console.error(
                    "Angelix report history load failed:",
                    error
                );

                reports = [];

                updateStatistics();

                renderReports();

                showToast(
                    "Unable to load report history.",
                    "error"
                );

            } finally {

                loading = false;

                setLoadingState(
                    false
                );
            }
        }


        function getEmbeddedReports() {
            /*
             * Supported locations:
             *
             * window.ANGELIX_REPORTS
             * #angelixReportHistoryData
             */

            if (
                Array.isArray(
                    window.ANGELIX_REPORTS
                )
            ) {
                return (
                    window.ANGELIX_REPORTS
                );
            }

            const dataElement =
                document.getElementById(
                    "angelixReportHistoryData"
                );

            if (!dataElement) {
                return null;
            }

            try {
                const parsed =
                    JSON.parse(
                        dataElement.textContent ||
                        "[]"
                    );

                return Array.isArray(
                    parsed
                )
                    ? parsed
                    : null;

            } catch (error) {

                console.error(
                    "Unable to parse report history data:",
                    error
                );

                return null;
            }
        }


        function extractReportsFromHTML(
            html
        ) {
            /*
             * This supports a JSON script element in a
             * server-rendered copy of the page.
             */

            try {

                const parser =
                    new DOMParser();

                const documentCopy =
                    parser.parseFromString(
                        html,
                        "text/html"
                    );

                const dataElement =
                    documentCopy.getElementById(
                        "angelixReportHistoryData"
                    );

                if (!dataElement) {
                    return null;
                }

                const parsed =
                    JSON.parse(
                        dataElement.textContent ||
                        "[]"
                    );

                return Array.isArray(
                    parsed
                )
                    ? parsed
                    : null;

            } catch (error) {

                console.error(
                    "Unable to extract report history data:",
                    error
                );

                return null;
            }
        }


        function normalizeReports(
            items
        ) {
            return items
                .filter(
                    item =>
                        item &&
                        typeof item ===
                        "object"
                )
                .map(
                    item => {

                        const normalizedStatus =
                            normalizeStatus(
                                item
                            );

                        return {
                            ...item,

                            id:
                                item.id,

                            name:
                                getReportName(
                                    item
                                ),

                            type:
                                getReportType(
                                    item
                                ),

                            typeLabel:
                                getReportTypeLabel(
                                    item
                                ),

                            period:
                                formatPeriod(
                                    item
                                ),

                            format:
                                getFileFormat(
                                    item
                                ),

                            created:
                                formatDate(
                                    item.created_at ||
                                    item.created
                                ),

                            status:
                                normalizedStatus,

                            size:
                                formatFileSize(
                                    item.file_size ||
                                    item.size
                                ),
                        };
                    }
                );
        }


        function setLoadingState(
            isLoading
        ) {
            if (!refreshBtn) {
                return;
            }

            refreshBtn.disabled =
                isLoading;

            refreshBtn.classList.toggle(
                "rotating",
                isLoading
            );
        }


        /* =====================================================
           FILTERING
        ===================================================== */

        function getFilteredReports() {

            const search =
                (
                    searchInput?.value ||
                    ""
                )
                    .trim()
                    .toLowerCase();

            const reportType =
                (
                    reportTypeFilter?.value ||
                    "all"
                )
                    .toLowerCase();

            const status =
                (
                    statusFilter?.value ||
                    "all"
                )
                    .toLowerCase();

            const format =
                (
                    formatFilter?.value ||
                    "all"
                )
                    .toLowerCase();

            const dateRange =
                (
                    dateFilter?.value ||
                    "all"
                )
                    .toLowerCase();

            const now =
                new Date();

            return reports.filter(
                report => {

                    /* -----------------------------------------
                       Search
                    ----------------------------------------- */

                    if (search) {

                        const haystack =
                            [
                                report.name,
                                report.typeLabel,
                                report.type,
                                report.period,
                                report.format,
                                report.status,
                                report.id,
                            ]
                                .join(" ")
                                .toLowerCase();

                        if (
                            !haystack.includes(
                                search
                            )
                        ) {
                            return false;
                        }
                    }

                    /* -----------------------------------------
                       Report type
                    ----------------------------------------- */

                    if (
                        reportType !==
                        "all"
                    ) {

                        if (
                            String(
                                report.type
                            ).toLowerCase() !==
                            reportType
                        ) {
                            return false;
                        }
                    }

                    /* -----------------------------------------
                       Status
                    ----------------------------------------- */

                    if (
                        status !==
                        "all"
                    ) {

                        const normalized =
                            normalizeStatus(
                                report
                            );

                        if (
                            normalized !==
                            status
                        ) {
                            return false;
                        }
                    }

                    /* -----------------------------------------
                       Format
                    ----------------------------------------- */

                    if (
                        format !==
                        "all"
                    ) {

                        if (
                            String(
                                report.format
                            ).toLowerCase() !==
                            format
                        ) {
                            return false;
                        }
                    }

                    /* -----------------------------------------
                       Date range
                    ----------------------------------------- */

                    if (
                        dateRange !==
                        "all"
                    ) {

                        const created =
                            new Date(
                                report.created_at ||
                                report.created
                            );

                        if (
                            Number.isNaN(
                                created.getTime()
                            )
                        ) {
                            return false;
                        }

                        const difference =
                            now.getTime() -
                            created.getTime();

                        const days =
                            difference /
                            (
                                1000 *
                                60 *
                                60 *
                                24
                            );

                        if (
                            dateRange ===
                            "7" &&
                            days >
                            7
                        ) {
                            return false;
                        }

                        if (
                            dateRange ===
                            "30" &&
                            days >
                            30
                        ) {
                            return false;
                        }

                        if (
                            dateRange ===
                            "90" &&
                            days >
                            90
                        ) {
                            return false;
                        }
                    }

                    return true;
                }
            );
        }


        /* =====================================================
           RENDER REPORTS
        ===================================================== */

        function renderReports() {

            if (!tableBody) {
                return;
            }

            filteredReports =
                getFilteredReports();

            const totalPages =
                Math.max(
                    1,
                    Math.ceil(
                        filteredReports.length /
                        PAGE_SIZE
                    )
                );

            if (
                currentPage >
                totalPages
            ) {
                currentPage =
                    totalPages;
            }

            const startIndex =
                (
                    currentPage -
                    1
                ) *
                PAGE_SIZE;

            const pageReports =
                filteredReports.slice(
                    startIndex,
                    startIndex +
                    PAGE_SIZE
                );

            tableBody.innerHTML =
                "";

            pageReports.forEach(
                report => {

                    tableBody.appendChild(
                        createReportRow(
                            report
                        )
                    );
                }
            );

            updateEmptyState(
                filteredReports.length ===
                0
            );

            updatePagination(
                filteredReports.length,
                startIndex,
                pageReports.length,
                totalPages
            );

            updateBulkSelection();
        }


        function createReportRow(
            report
        ) {

            const row =
                document.createElement(
                    "tr"
                );

            const status =
                normalizeStatus(
                    report
                );

            const canDownload =
                status ===
                "completed";

            const viewUrl =
                getViewURL(
                    report.id
                );

            const downloadUrl =
                getDownloadURL(
                    report.id
                );

            row.innerHTML = `
                <td class="checkbox-column">
                    <label class="table-checkbox">
                        <input
                            type="checkbox"
                            class="report-row-checkbox"
                            value="${escapeHTML(
                                report.id
                            )}"
                            aria-label="Select report ${escapeHTML(
                                report.name
                            )}"
                        >
                        <span></span>
                    </label>
                </td>

                <td>
                    <div class="report-name-cell">

                        <span class="report-file-icon">
                            ${getFormatIcon(
                                report.format
                            )}
                        </span>

                        <div>
                            <strong>
                                ${escapeHTML(
                                    report.name
                                )}
                            </strong>

                            <small>
                                #${escapeHTML(
                                    report.id
                                )}
                            </small>
                        </div>

                    </div>
                </td>

                <td>
                    <span class="report-type-label">
                        ${escapeHTML(
                            report.typeLabel
                        )}
                    </span>
                </td>

                <td>
                    ${escapeHTML(
                        report.period
                    )}
                </td>

                <td>
                    <span class="report-format-badge">
                        ${escapeHTML(
                            report.format
                        )}
                    </span>
                </td>

                <td>
                    ${escapeHTML(
                        report.created
                    )}
                </td>

                <td>
                    <span
                        class="status-badge ${getStatusClass(
                            status
                        )}"
                    >
                        <span class="status-dot"></span>
                        ${escapeHTML(
                            getStatusLabel(
                                status
                            )
                        )}
                    </span>
                </td>

                <td>
                    ${escapeHTML(
                        report.size
                    )}
                </td>

                <td>

                    <div class="table-actions">

                        <button
                            type="button"
                            class="table-action-btn"
                            data-action="view"
                            data-report-id="${escapeHTML(
                                report.id
                            )}"
                            title="View report"
                            aria-label="View report"
                        >
                            👁
                        </button>

                        <button
                            type="button"
                            class="table-action-btn"
                            data-action="download"
                            data-report-id="${escapeHTML(
                                report.id
                            )}"
                            title="Download report"
                            aria-label="Download report"
                            ${
                                canDownload
                                    ? ""
                                    : "disabled"
                            }
                        >
                            ↓
                        </button>

                        <button
                            type="button"
                            class="table-action-btn"
                            data-action="delete"
                            data-report-id="${escapeHTML(
                                report.id
                            )}"
                            title="Delete report"
                            aria-label="Delete report"
                        >
                            🗑
                        </button>

                    </div>

                </td>
            `;

            attachRowEvents(
                row
            );

            return row;
        }


        /* =====================================================
           EMPTY STATE
        ===================================================== */

        function updateEmptyState(
            isEmpty
        ) {

            if (!emptyState) {
                return;
            }

            emptyState.hidden =
                !isEmpty;

            const wrapper =
                tableBody?.closest(
                    ".history-table-wrapper"
                );

            if (wrapper) {
                wrapper.style.display =
                    isEmpty
                        ? "none"
                        : "";
            }
        }


        /* =====================================================
           PAGINATION
        ===================================================== */

        function updatePagination(
            total,
            startIndex,
            visibleCount,
            totalPages
        ) {

            if (
                showingTotal
            ) {
                showingTotal.textContent =
                    total;
            }

            if (
                total ===
                0
            ) {

                if (
                    showingFrom
                ) {
                    showingFrom.textContent =
                        "0";
                }

                if (
                    showingTo
                ) {
                    showingTo.textContent =
                        "0";
                }

            } else {

                if (
                    showingFrom
                ) {
                    showingFrom.textContent =
                        startIndex +
                        1;
                }

                if (
                    showingTo
                ) {
                    showingTo.textContent =
                        startIndex +
                        visibleCount;
                }
            }

            if (
                previousPageBtn
            ) {
                previousPageBtn.disabled =
                    currentPage <=
                    1;
            }

            if (
                nextPageBtn
            ) {
                nextPageBtn.disabled =
                    currentPage >=
                    totalPages;
            }

            document
                .querySelectorAll(
                    ".pagination-page"
                )
                .forEach(
                    button => {

                        const page =
                            Number(
                                button.dataset.page
                            );

                        button.classList.toggle(
                            "active",
                            page ===
                            currentPage
                        );
                    }
                );
        }


        /* =====================================================
           ROW EVENTS
        ===================================================== */

        function attachRowEvents(
            row
        ) {

            const checkbox =
                row.querySelector(
                    ".report-row-checkbox"
                );

            checkbox?.addEventListener(
                "change",
                updateBulkSelection
            );

            row
                .querySelectorAll(
                    ".table-action-btn"
                )
                .forEach(
                    button => {

                        button.addEventListener(
                            "click",
                            () => {

                                const action =
                                    button.dataset.action;

                                const reportId =
                                    button.dataset.reportId;

                                handleReportAction(
                                    action,
                                    reportId
                                );
                            }
                        );
                    }
                );
        }


        /* =====================================================
           ROW ACTIONS
        ===================================================== */

        function handleReportAction(
            action,
            reportId
        ) {

            const report =
                reports.find(
                    item =>
                        String(
                            item.id
                        ) ===
                        String(
                            reportId
                        )
                );

            if (!report) {

                showToast(
                    "Report not found.",
                    "error"
                );

                return;
            }

            switch (
                action
            ) {

                case "view":
                    window.location.href =
                        getViewURL(
                            report.id
                        );
                    break;

                case "download":
                    downloadReport(
                        report
                    );
                    break;

                case "delete":
                    openDeleteModal(
                        [report.id]
                    );
                    break;

                default:
                    break;
            }
        }


        /* =====================================================
           URL HELPERS
        ===================================================== */

        function getViewURL(
            reportId
        ) {

            return (
                `/organizations/${organizationId}` +
                `/reports/${reportId}`
            );
        }


        function getDownloadURL(
            reportId
        ) {

            return (
                `/organizations/${organizationId}` +
                `/reports/${reportId}/download`
            );
        }


        function getDeleteURL(
            reportId
        ) {

            return (
                `/organizations/${organizationId}` +
                `/reports/${reportId}/delete`
            );
        }


        /* =====================================================
           DOWNLOAD
        ===================================================== */

        function downloadReport(
            report
        ) {

            const status =
                normalizeStatus(
                    report
                );

            if (
                status !==
                "completed"
            ) {

                showToast(
                    "This report is not ready for download.",
                    "error"
                );

                return;
            }

            const url =
                getDownloadURL(
                    report.id
                );

            window.location.href =
                url;
        }


        /* =====================================================
           BULK SELECTION
        ===================================================== */

        function getSelectedReportIds() {

            return Array.from(
                document.querySelectorAll(
                    ".report-row-checkbox:checked"
                )
            ).map(
                checkbox =>
                    String(
                        checkbox.value
                    )
            );
        }


        function updateBulkSelection() {

            const selected =
                getSelectedReportIds();

            if (
                selectedCountElement
            ) {
                selectedCountElement.textContent =
                    selected.length;
            }

            if (
                bulkToolbar
            ) {
                bulkToolbar.hidden =
                    selected.length ===
                    0;
            }

            if (
                selectAllCheckbox
            ) {

                const visibleCheckboxes =
                    Array.from(
                        document.querySelectorAll(
                            ".report-row-checkbox"
                        )
                    );

                selectAllCheckbox.checked =
                    visibleCheckboxes.length >
                    0 &&
                    visibleCheckboxes.every(
                        checkbox =>
                            checkbox.checked
                    );

                selectAllCheckbox.indeterminate =
                    selected.length >
                    0 &&
                    !selectAllCheckbox.checked;
            }
        }


        selectAllCheckbox?.addEventListener(
            "change",
            () => {

                const checked =
                    selectAllCheckbox.checked;

                document
                    .querySelectorAll(
                        ".report-row-checkbox"
                    )
                    .forEach(
                        checkbox => {
                            checkbox.checked =
                                checked;
                        }
                    );

                updateBulkSelection();
            }
        );


        /* =====================================================
           BULK DOWNLOAD
        ===================================================== */

        bulkDownloadBtn?.addEventListener(
            "click",
            () => {

                const selected =
                    getSelectedReportIds();

                if (
                    selected.length ===
                    0
                ) {

                    showToast(
                        "Select at least one report.",
                        "error"
                    );

                    return;
                }

                const selectedReports =
                    reports.filter(
                        report =>
                            selected.includes(
                                String(
                                    report.id
                                )
                            )
                    );

                const downloadable =
                    selectedReports.filter(
                        report =>
                            normalizeStatus(
                                report
                            ) ===
                            "completed"
                    );

                if (
                    downloadable.length ===
                    0
                ) {

                    showToast(
                        "None of the selected reports are ready for download.",
                        "error"
                    );

                    return;
                }

                /*
                 * Browsers may block multiple downloads if triggered
                 * too quickly. A small delay makes the behavior more
                 * reliable.
                 */

                downloadable.forEach(
                    (
                        report,
                        index
                    ) => {

                        setTimeout(
                            () => {

                                window.open(
                                    getDownloadURL(
                                        report.id
                                    ),
                                    "_blank"
                                );

                            },
                            index *
                            400
                        );
                    }
                );
            }
        );


        /* =====================================================
           DELETE MODAL
        ===================================================== */

        function openDeleteModal(
            ids
        ) {

            reportsToDelete =
                ids.map(
                    id =>
                        String(id)
                );

            if (
                deleteMessage
            ) {

                const count =
                    reportsToDelete.length;

                deleteMessage.textContent =
                    count === 1
                        ? "Are you sure you want to delete this report? This action cannot be undone."
                        : `Are you sure you want to delete ${count} reports? This action cannot be undone.`;
            }

            if (
                deleteModal
            ) {

                deleteModal.hidden =
                    false;

                document.body.classList.add(
                    "modal-open"
                );
            }
        }


        function closeDeleteModal() {

            reportsToDelete =
                [];

            if (
                deleteModal
            ) {

                deleteModal.hidden =
                    true;

                document.body.classList.remove(
                    "modal-open"
                );
            }
        }


        closeDeleteModalBtn?.addEventListener(
            "click",
            closeDeleteModal
        );

        cancelDeleteBtn?.addEventListener(
            "click",
            closeDeleteModal
        );

        deleteModal?.addEventListener(
            "click",
            event => {

                if (
                    event.target ===
                    deleteModal
                ) {
                    closeDeleteModal();
                }
            }
        );


        /* =====================================================
           REAL DELETE
        ===================================================== */

        confirmDeleteBtn?.addEventListener(
            "click",
            async () => {

                if (
                    reportsToDelete.length ===
                    0
                ) {
                    return;
                }

                const ids =
                    [...reportsToDelete];

                confirmDeleteBtn.disabled =
                    true;

                try {

                    let successCount =
                        0;

                    for (
                        const reportId
                        of ids
                    ) {

                                                const csrfToken =
                            getCSRFToken();

                        if (!csrfToken) {
                            throw new Error(
                                "CSRF token was not found."
                            );
                        }

                        const response =
                            await fetch(
                                getDeleteURL(
                                    reportId
                                ),
                                {
                                    method:
                                        "POST",

                                    credentials:
                                        "same-origin",

                                    headers: {
                                        "Content-Type":
                                            "application/json",

                                        "X-Requested-With":
                                            "XMLHttpRequest",

                                        "X-CSRFToken":
                                            csrfToken,
                                    },

                                    body:
                                        JSON.stringify({})
                                }
                            );

                        /*
                         * Flask redirects after successful deletion.
                         * A redirect still results in an OK response.
                         */

                        if (
                            response.ok
                        ) {
                            successCount +=
                                1;
                        }
                    }

                    reports =
                        reports.filter(
                            report =>
                                !ids.includes(
                                    String(
                                        report.id
                                    )
                                )
                        );

                    closeDeleteModal();

                    if (
                        selectAllCheckbox
                    ) {
                        selectAllCheckbox.checked =
                            false;
                    }

                    updateStatistics();

                    renderReports();

                    if (
                        successCount ===
                        ids.length
                    ) {

                        showToast(
                            `${successCount} report${
                                successCount ===
                                1
                                    ? ""
                                    : "s"
                            } deleted successfully.`,
                            "success"
                        );

                    } else {

                        showToast(
                            `${successCount} of ${ids.length} reports deleted.`,
                            "error"
                        );
                    }

                } catch (
                    error
                ) {

                    console.error(
                        "Report deletion failed:",
                        error
                    );

                    showToast(
                        "Unable to delete the selected reports.",
                        "error"
                    );

                } finally {

                    confirmDeleteBtn.disabled =
                        false;
                }
            }
        );


        bulkDeleteBtn?.addEventListener(
            "click",
            () => {

                const selected =
                    getSelectedReportIds();

                if (
                    selected.length ===
                    0
                ) {

                    showToast(
                        "Select at least one report.",
                        "error"
                    );

                    return;
                }

                openDeleteModal(
                    selected
                );
            }
        );


        /* =====================================================
           SEARCH
        ===================================================== */

        searchInput?.addEventListener(
            "input",
            () => {

                if (
                    clearSearchBtn
                ) {

                    clearSearchBtn.hidden =
                        !searchInput.value;
                }

                currentPage =
                    1;

                renderReports();
            }
        );


        clearSearchBtn?.addEventListener(
            "click",
            () => {

                if (
                    searchInput
                ) {

                    searchInput.value =
                        "";
                }

                clearSearchBtn.hidden =
                    true;

                currentPage =
                    1;

                renderReports();

                searchInput?.focus();
            }
        );


        /* =====================================================
           FILTERS
        ===================================================== */

        [
            reportTypeFilter,
            statusFilter,
            formatFilter,
            dateFilter,
        ].forEach(
            filter => {

                filter?.addEventListener(
                    "change",
                    () => {

                        currentPage =
                            1;

                        renderReports();
                    }
                );
            }
        );


        function clearFilters() {

            if (
                searchInput
            ) {
                searchInput.value =
                    "";
            }

            if (
                reportTypeFilter
            ) {
                reportTypeFilter.value =
                    "all";
            }

            if (
                statusFilter
            ) {
                statusFilter.value =
                    "all";
            }

            if (
                formatFilter
            ) {
                formatFilter.value =
                    "all";
            }

            if (
                dateFilter
            ) {
                dateFilter.value =
                    "all";
            }

            if (
                clearSearchBtn
            ) {
                clearSearchBtn.hidden =
                    true;
            }

            currentPage =
                1;

            renderReports();
        }


        clearFiltersBtn?.addEventListener(
            "click",
            clearFilters
        );

        resetFiltersBtn?.addEventListener(
            "click",
            clearFilters
        );


        /* =====================================================
           PAGINATION
        ===================================================== */

        previousPageBtn?.addEventListener(
            "click",
            () => {

                if (
                    currentPage >
                    1
                ) {

                    currentPage -=
                        1;

                    renderReports();
                }
            }
        );


        nextPageBtn?.addEventListener(
            "click",
            () => {

                const total =
                    getFilteredReports()
                        .length;

                const totalPages =
                    Math.max(
                        1,
                        Math.ceil(
                            total /
                            PAGE_SIZE
                        )
                    );

                if (
                    currentPage <
                    totalPages
                ) {

                    currentPage +=
                        1;

                    renderReports();
                }
            }
        );


        document
            .querySelectorAll(
                ".pagination-page"
            )
            .forEach(
                button => {

                    button.addEventListener(
                        "click",
                        () => {

                            const page =
                                Number(
                                    button.dataset.page
                                );

                            if (
                                Number.isInteger(
                                    page
                                )
                            ) {

                                currentPage =
                                    page;

                                renderReports();
                            }
                        }
                    );
                }
            );


        /* =====================================================
           STATISTICS
        ===================================================== */

        function updateStatistics() {

            const totalElement =
                document.getElementById(
                    "historyTotalReports"
                );

            const readyElement =
                document.getElementById(
                    "historyReadyReports"
                );

            const processingElement =
                document.getElementById(
                    "historyProcessingReports"
                );

            const monthlyElement =
                document.getElementById(
                    "historyMonthlyReports"
                );

            const ready =
                reports.filter(
                    report =>
                        normalizeStatus(
                            report
                        ) ===
                        "completed"
                ).length;

            const processing =
                reports.filter(
                    report => {

                        const status =
                            normalizeStatus(
                                report
                            );

                        return (
                            status ===
                            "processing" ||
                            status ===
                            "pending"
                        );
                    }
                ).length;

            const now =
                new Date();

            const monthly =
                reports.filter(
                    report => {

                        const created =
                            new Date(
                                report.created_at ||
                                report.created
                            );

                        if (
                            Number.isNaN(
                                created.getTime()
                            )
                        ) {
                            return false;
                        }

                        return (
                            created.getMonth() ===
                            now.getMonth() &&
                            created.getFullYear() ===
                            now.getFullYear()
                        );
                    }
                ).length;

            if (
                totalElement
            ) {
                totalElement.textContent =
                    reports.length;
            }

            if (
                readyElement
            ) {
                readyElement.textContent =
                    ready;
            }

            if (
                processingElement
            ) {
                processingElement.textContent =
                    processing;
            }

            if (
                monthlyElement
            ) {
                monthlyElement.textContent =
                    monthly;
            }
        }


        /* =====================================================
           REFRESH
        ===================================================== */

        refreshBtn?.addEventListener(
            "click",
            async () => {

                await loadReports();

                showToast(
                    "Report history refreshed successfully.",
                    "success"
                );
            }
        );


        /* =====================================================
           TOAST
        ===================================================== */

        function showToast(
            message,
            type = "info"
        ) {

            if (
                !toastContainer
            ) {
                return;
            }

            const toast =
                document.createElement(
                    "div"
                );

            toast.className =
                `toast toast-${type}`;

            let icon =
                "i";

            if (
                type ===
                "success"
            ) {
                icon =
                    "✓";
            } else if (
                type ===
                "error"
            ) {
                icon =
                    "!";
            }

            toast.innerHTML = `
                <span class="toast-icon">
                    ${icon}
                </span>

                <span class="toast-message"></span>

                <button
                    type="button"
                    class="toast-close"
                    aria-label="Close notification"
                >
                    ×
                </button>
            `;

            const messageElement =
                toast.querySelector(
                    ".toast-message"
                );

            if (
                messageElement
            ) {
                messageElement.textContent =
                    message;
            }

            toastContainer.appendChild(
                toast
            );

            requestAnimationFrame(
                () => {

                    toast.classList.add(
                        "show"
                    );
                }
            );

            toast.querySelector(
                ".toast-close"
            )?.addEventListener(
                "click",
                () =>
                    removeToast(
                        toast
                    )
            );

            setTimeout(
                () =>
                    removeToast(
                        toast
                    ),
                4000
            );
        }


        function removeToast(
            toast
        ) {

            if (!toast) {
                return;
            }

            toast.classList.remove(
                "show"
            );

            setTimeout(
                () => {

                    if (
                        toast.parentNode
                    ) {
                        toast.remove();
                    }
                },
                250
            );
        }


        /* =====================================================
           THEME SUPPORT
        ===================================================== */

        function applyThemeState() {

            const theme =
                document.documentElement
                    .getAttribute(
                        "data-theme"
                    );

            document.body.dataset.reportTheme =
                theme ||
                "light";
        }


        applyThemeState();


        const themeObserver =
            new MutationObserver(
                mutations => {

                    mutations.forEach(
                        mutation => {

                            if (
                                mutation.type ===
                                "attributes" &&
                                mutation.attributeName ===
                                "data-theme"
                            ) {
                                applyThemeState();
                            }
                        }
                    );
                }
            );


        themeObserver.observe(
            document.documentElement,
            {
                attributes:
                    true,
            }
        );


        /* =====================================================
           INITIALIZATION
        ===================================================== */

        updateStatistics();

        renderReports();

        loadReports();


        /* =====================================================
           PUBLIC API
        ===================================================== */

        window.angelixReportHistory = {
            getReports:
                () => reports,

            refresh:
                loadReports,

            render:
                renderReports,

            showToast:
                showToast,
        };
    }
);